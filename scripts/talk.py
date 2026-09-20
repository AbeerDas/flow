"""Hold Right Option, say what you want, let go.

    .venv/bin/python scripts/talk.py          # says what it would do
    .venv/bin/python scripts/talk.py --go     # lets it act
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.decide import describe, engine as make_engine
from flow.listen import PERMISSION, SAMPLE_RATE, Ears, Trigger
from flow.notify import ask, banner, sound
from flow.registry import Registry
from flow.run import execute

commit = "--go" in sys.argv

if "--mic-test" in sys.argv:
    # Proves the microphone and the speech model without involving the key.
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
    print(f'heard "{heard}"' if heard else "heard nothing. Speak closer, or louder.")
    sys.exit(0)

if "--key-test" in sys.argv:
    # Prove the key is getting through before involving speech at all.
    with Trigger() as trigger:
        print("press Right Option a few times. ctrl-c to stop.")
        try:
            while True:
                if trigger.wait_for_press(timeout=5.0):
                    print("  got it, held…", end="", flush=True)
                    while trigger.held.is_set():
                        time.sleep(0.02)
                    print(" released")
                elif not trigger.saw_any.is_set():
                    sys.exit("\n" + PERMISSION)
        except KeyboardInterrupt:
            sys.exit("\nstopped")

print("loading, first run downloads the speech model…")
ears = Ears()
adapter = MacAdapter()
engine = make_engine()
registry = Registry()
ears.open_microphone()  # fail here, at launch, rather than mid-press
print(f"ready. hold Right Option and speak. ctrl-c to stop. {'acting' if commit else 'dry run'}.\n")
banner("Flow is listening", "Hold Right Option anywhere and speak.")
sound("done")


def confirm(entry, confidence, text):
    detail = f' with "{text}"' if text else ""
    question = f"{describe(entry)}{detail}"
    if sys.stdin and sys.stdin.isatty():
        return input(f"   risky: {question}. run it? [y/N] ").strip().lower() == "y"
    return ask("Flow wants to do this", f"{question}\n\nConfidence {confidence:.0%}.")


def announce(step):
    detail = f' with "{step.text}"' if step.text else ""
    print(f"   {step.confidence:.2f}  {describe(step.entry)}{detail}")


idle = 0.0
warned = False

with Trigger() as trigger:
    try:
        while True:
            if not trigger.wait_for_press(timeout=5.0):
                # Silence is ambiguous. Nobody pressing anything looks exactly
                # like the listener not being permitted, so say so once, late,
                # and carry on waiting either way.
                idle += 5.0
                if idle >= 30.0 and not trigger.saw_any.is_set() and not warned:
                    print(PERMISSION + "\n\nStill waiting, in case you were just idle.\n")
                    warned = True
                continue
            idle = 0.0
            sound("listening")
            print("listening…", end="", flush=True)
            audio = ears.record_while(trigger.held)
            if len(audio) < SAMPLE_RATE // 5:
                sound("nothing")
                print(f"\r too short ({len(audio)} samples), hold the key while you speak   ")
                continue
            started = time.time()
            said = ears.transcribe(audio)
            heard_ms = (time.time() - started) * 1000
            if not said:
                sound("nothing")
                print("\r nothing heard   ")
                continue
            sound("heard")
            print(f'\r heard "{said}"  ({heard_ms:.0f} ms)')
            try:
                run = execute(said, adapter, engine, registry, commit=commit,
                              confirm=confirm, on_step=announce)
            except Exception as error:
                # One bad request must not take the listener down with it.
                sound("nothing")
                banner("Flow hit a problem", str(error)[:150])
                print(f"   failed: {error}\n")
                continue
            print(f"   {run.verdict}\n")
            did = "; ".join(s.outcome for s in run.steps) or run.verdict
            sound("done" if run.steps else "nothing")
            banner(said, did)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        adapter.close()
