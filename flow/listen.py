"""Hold a key, speak, let go.

Push to talk rather than always listening, so the microphone is only ever open
while a key is physically held down. Nothing is recorded otherwise and nothing
leaves the machine.
"""

from __future__ import annotations

import threading
import time

SAMPLE_RATE = 16000
MODEL = "mlx-community/parakeet-tdt-0.6b-v3"


class Ears:
    """Speech to text, on this machine."""

    def __init__(self, model_id: str = MODEL):
        from parakeet_mlx import from_pretrained

        self.model = from_pretrained(model_id)

    def transcribe(self, audio) -> str:
        import mlx.core as mx

        with self.model.transcribe_stream(context_size=(256, 256)) as stream:
            stream.add_audio(mx.array(audio))
            return (stream.result.text or "").strip()

    def record_while(self, held: threading.Event, max_seconds: float = 20.0) -> object:
        """Everything spoken between the key going down and coming up."""
        import numpy as np
        import sounddevice as sd

        frames: list = []
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=lambda data, *_: frames.append(data.copy()),
        ):
            deadline = time.time() + max_seconds
            while held.is_set() and time.time() < deadline:
                time.sleep(0.01)
        if not frames:
            return np.zeros(0, dtype="float32")
        return np.concatenate(frames)[:, 0]


class Trigger:
    """One key, held. Right Option, because nothing else wants it."""

    def __init__(self, key_name: str = "alt_r"):
        from pynput import keyboard

        self.keyboard = keyboard
        self.key = getattr(keyboard.Key, key_name)
        self.held = threading.Event()
        self.pressed = threading.Event()
        self.listener = keyboard.Listener(on_press=self._down, on_release=self._up)

    def _down(self, key):
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
