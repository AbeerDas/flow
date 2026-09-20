"""Hold Right Option, speak, keep holding. It acts on each phrase as you finish it.

    .venv/bin/python scripts/talk.py            # says what it would do
    .venv/bin/python scripts/talk.py --go       # lets it act
    .venv/bin/python scripts/talk.py --mic-test # microphone and speech only
    .venv/bin/python scripts/talk.py --key-test # the key only
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.decide import describe, engine as make_engine
from flow.listen import PERMISSION, Ears, Trigger
from flow.notify import ask, banner, sound
from flow.journal import journal
from flow.registry import Registry, Reversibility
from flow.run import execute
from flow.text import unhomophone

commit = "--go" in sys.argv
# --trust lets undoable things through without asking; permanent still stops.
# --reckless stops asking about anything at all.
trust = Reversibility.FREE
if "--trust" in sys.argv:
    trust = Reversibility.UNDOABLE
if "--reckless" in sys.argv:
    trust = Reversibility.PERMANENT


if "--mic-test" in sys.argv:
    import numpy as np

    print("loading the speech model…")
    ears = Ears()
    print("say something, recording for 4 seconds…")
    clip = ears.record_for(4.0)
    level = float(np.abs(clip).max()) if len(clip) else 0.0
    print(f"captured {len(clip)} samples, peak level {level:.3f}")
    if level < 0.01:
        sys.exit("that is silence. Check the input device and microphone permission.")
    heard = ears.transcribe(clip)
    sys.exit(f'heard "{heard}"' if heard else "heard nothing. Speak closer, or louder.")

if "--key-test" in sys.argv:
    with Trigger() as trigger:
        print("press Right Option a few times. ctrl-c to stop.")
        try:
            while True:
                if trigger.wait_for_press(timeout=5.0):
                    print("  got it, held…", end="", flush=True)
                    while trigger.held.is_set():
                        time.sleep(0.02)
                    print(" released")
        except KeyboardInterrupt:
            sys.exit("\nstopped")


def listen(overlay):
    """Everything except the window. Runs beside it, never on its thread."""
    print("loading the speech model…")
    ears = Ears()
    ears.open_microphone()
    adapter = MacAdapter()
    engine = make_engine()
    registry = Registry()
    mode = "acting" if commit else "dry run"
    if commit and trust is not Reversibility.FREE:
        mode += f", trusting up to {trust.name.lower()}"
    journal.fresh()
    journal.write("ready", mode=mode, trust=trust.name)
    print(f"ready. hold Right Option anywhere. {mode}. journal: {journal.path}\n")
    banner("Flow is listening", "Hold Right Option anywhere and speak.")

    def confirm(entry, confidence, text):
        detail = f' with "{text}"' if text else ""
        question = f"{describe(entry)}{detail}"
        overlay.tint("working")
        overlay.say("Waiting for you…")
        return ask("Flow wants to do this", f"{question}\n\nConfidence {confidence:.0%}.")

    def meter(held):
        """Keep the bars moving for as long as the key is down."""
        while held.is_set():
            overlay.meter(ears.level())
            time.sleep(0.05)

    with Trigger() as trigger:
        while True:
            if not trigger.wait_for_press(timeout=5.0):
                continue
            sound("listening")
            overlay.tint("listening")
            overlay.say("Listening…")
            overlay.show()
            threading.Thread(target=meter, args=(trigger.held,), daemon=True).start()

            acted = 0
            for audio in ears.phrases_while(trigger.held):
                said = ears.transcribe(audio)
                if not said:
                    continue
                heard = said
                said = unhomophone(said)
                if said != heard:
                    journal.write("corrected", heard=heard, read_as=said)
                journal.write("heard", said=said, samples=len(audio))
                sound("heard")
                overlay.say(said)
                overlay.tint("working")
                print(f'heard "{said}"')
                try:
                    run = execute(
                        said, adapter, engine, registry, commit=commit,
                        trust=trust, confirm=confirm,
                    )
                except Exception as error:
                    overlay.tint("nothing")
                    overlay.say(f"Failed: {str(error)[:60]}")
                    print(f"   failed: {error}")
                    continue
                journal.write("finished", said=said, verdict=run.verdict,
                              steps=[s.outcome for s in run.steps])
                did = "; ".join(s.outcome for s in run.steps) or run.verdict
                if not run.steps and run.offered:
                    # Say what it was looking at, so a miss can be read rather
                    # than guessed at.
                    print("   it was choosing between:")
                    for option in run.offered:
                        print(f"     - {option}")
                acted += len(run.steps)
                overlay.tint("done" if run.steps else "nothing")
                overlay.say(did[:90])
                sound("done" if run.steps else "nothing")
                print(f"   {did}")
                # Back to listening, because the key is still down.
                if trigger.held.is_set():
                    time.sleep(0.4)
                    overlay.tint("listening")
                    overlay.say("Listening…")

            overlay.tint("done" if acted else "nothing")
            if not acted:
                overlay.say("Nothing to do")
            time.sleep(1.2)
            overlay.hide()


if "--no-overlay" in sys.argv:

    class Quiet:
        def __getattr__(self, _):
            return lambda *a, **k: None

    listen(Quiet())
else:
    from flow.overlay import run as run_overlay

    run_overlay(listen)
