"""Hold a key, speak, let go.

Push to talk rather than always listening, so the microphone is only ever open
while a key is physically held down. Nothing is recorded otherwise and nothing
leaves the machine.
"""

from __future__ import annotations

import os
import threading
import time

SAMPLE_RATE = 16000
# Quieter than this counts as not speaking. A laptop microphone idles well
# under it and speech at arm's length sits well over.
SILENCE_LEVEL = 0.015
# A pause this long ends a phrase, and it acts on what was said before it.
PHRASE_GAP = 0.65
# Shorter than this is a cough, not an instruction.
MIN_PHRASE = 0.35
# Enough samples to fill one analysis window.
MIN_SAMPLES = SAMPLE_RATE // 5
# Kept recording past the key coming up, so the last word survives.
TAIL_SECONDS = 0.25
# v3 is multilingual and will happily render "youtube dot com" in Cyrillic.
# v2 is English only and does not. FLOW_SPEECH_MODEL overrides either way.
MODEL = os.environ.get("FLOW_SPEECH_MODEL", "mlx-community/parakeet-tdt-0.6b-v3")
ENGLISH_MODEL = "mlx-community/parakeet-tdt-0.6b-v2"


class Ears:
    """Speech to text, on this machine."""

    def __init__(self, model_id: str = MODEL):
        from parakeet_mlx import from_pretrained

        self.model = from_pretrained(model_id)
        self._stream = None
        self._frames: list = []
        self._keeping = False
        self._level = 0.0

    def transcribe(self, audio) -> str:
        """Samples in, words out.

        Straight through the spectrogram rather than the streaming interface,
        which returned an empty string for perfectly audible speech.
        """
        import mlx.core as mx
        import numpy as np
        from parakeet_mlx.audio import get_logmel

        # Below about a fifth of a second there are not enough samples to fill
        # one analysis window, and the failure is a negative dimension deep in
        # the transform rather than anything that names the cause.
        if len(audio) < MIN_SAMPLES:
            return ""
        audio = np.asarray(audio, dtype="float32")
        # A laptop microphone at arm's length peaks around a tenth of full
        # scale, which is quiet enough to transcribe as nothing.
        peak = float(np.abs(audio).max())
        if 0.0 < peak < 0.5:
            audio = audio * (0.9 / peak)
        mel = get_logmel(mx.array(audio), self.model.preprocessor_config)
        results = self.model.generate(mel)
        return (results[0].text or "").strip() if results else ""

    def open_microphone(self) -> None:
        """Open the input once and leave it open.

        Opening and closing around every press blocked on the teardown with
        the process alive and idle, needing a kill. One stream, started at
        launch, has no teardown to block on.

        The handle stays open while the program runs. Audio is only kept while
        the key is held and is dropped otherwise, so nothing is recorded
        between presses.
        """
        import sounddevice as sd

        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._collect,
            blocksize=int(SAMPLE_RATE * 0.05),
        )
        self._stream.start()

    def _collect(self, data, *_):
        if self._keeping:
            self._frames.append(data.copy())

    def _drain(self) -> list:
        """Take whatever has arrived since the last look."""
        taken, self._frames = self._frames, []
        return taken

    def level(self) -> float:
        """How loud it is right now, for something to draw."""
        return self._level

    def record_while(self, held: threading.Event, max_seconds: float = 20.0):
        """Everything spoken between the key going down and coming up.

        A short tail runs past the release, because the last word is usually
        still being said as the key comes up.
        """
        import numpy as np

        self.open_microphone()
        self._frames.clear()
        self._keeping = True
        try:
            deadline = time.time() + max_seconds
            while held.is_set() and time.time() < deadline:
                time.sleep(0.01)
            time.sleep(TAIL_SECONDS)
        finally:
            self._keeping = False
        frames = list(self._frames)
        self._frames.clear()
        if not frames:
            return np.zeros(0, dtype="float32")
        return np.concatenate(frames)[:, 0]

    def phrases_while(self, held: threading.Event, max_seconds: float = 120.0):
        """Speech, a phrase at a time, for as long as the key is held.

        A pause ends a phrase and it is handed over straight away, so a request
        is acted on while the next one is still being thought about. Holding
        the key through silence is allowed and costs nothing.
        """
        import numpy as np

        self.open_microphone()
        self._drain()
        self._keeping = True
        buffered: list = []
        quiet = 0.0
        loud = 0.0
        deadline = time.time() + max_seconds
        try:
            while held.is_set() and time.time() < deadline:
                time.sleep(0.05)
                arrived = self._drain()
                if not arrived:
                    continue
                block = np.concatenate(arrived)[:, 0]
                seconds = len(block) / SAMPLE_RATE
                peak = float(np.abs(block).max())
                self._level = peak
                if peak < SILENCE_LEVEL:
                    quiet += seconds
                else:
                    quiet = 0.0
                    loud += seconds
                buffered.append(block)
                if quiet >= PHRASE_GAP and loud >= MIN_PHRASE:
                    yield np.concatenate(buffered)
                    buffered, quiet, loud = [], 0.0, 0.0
            time.sleep(TAIL_SECONDS)
            rest = self._drain()
            if rest:
                buffered.append(np.concatenate(rest)[:, 0])
            if buffered and loud >= MIN_PHRASE:
                yield np.concatenate(buffered)
        finally:
            self._keeping = False
            self._level = 0.0

    def record_for(self, seconds: float):
        """A fixed clip, for proving the microphone works on its own."""
        import sounddevice as sd

        clip = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
        return clip[:, 0]


PERMISSION = """No key presses are reaching this process.

macOS needs Input Monitoring as well as Accessibility, and they are separate
switches. System Settings > Privacy & Security > Input Monitoring, then add the
application running this shell and restart it.

To check which application that is:
    ps -o comm= -p $(ps -o ppid= -p $PPID)"""


class Trigger:
    """One key, held. Right Option, because nothing else wants it."""

    def __init__(self, key_name: str = "alt_r"):
        from pynput import keyboard

        self.keyboard = keyboard
        self.key = getattr(keyboard.Key, key_name)
        self.held = threading.Event()
        # Nothing arriving at all means the listener is not permitted, which
        # macOS reports by silence rather than by an error.
        self.saw_any = threading.Event()
        self.pressed = threading.Event()
        self.listener = keyboard.Listener(on_press=self._down, on_release=self._up)

    def _down(self, key):
        self.saw_any.set()
        if key == self.key and not self.held.is_set():
            self.held.set()
            self.pressed.set()

    def _up(self, key):
        if key == self.key:
            self.held.clear()

    def __enter__(self):
        self.listener.start()
        return self

    def __exit__(self, *_):
        self.listener.stop()

    def wait_for_press(self, timeout: float | None = None) -> bool:
        self.pressed.clear()
        return self.pressed.wait(timeout)
