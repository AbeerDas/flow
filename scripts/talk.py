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
from flow.registry import Registry
from flow.run import execute

commit = "--go" in sys.argv

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
print(f"ready. hold Right Option and speak. ctrl-c to stop. {'acting' if commit else 'dry run'}.\n")


def confirm(entry, confidence, text):
    detail = f' with "{text}"' if text else ""
    return input(f"   risky: {describe(entry)}{detail}. run it? [y/N] ").strip().lower() == "y"


def announce(step):
    detail = f' with "{step.text}"' if step.text else ""
    print(f"   {step.confidence:.2f}  {describe(step.entry)}{detail}")


with Trigger() as trigger:
    try:
        while True:
            if not trigger.wait_for_press(timeout=5.0):
                if not trigger.saw_any.is_set():
                    print(PERMISSION)
                    break
                continue
            print("listening…", end="", flush=True)
            audio = ears.record_while(trigger.held)
            if len(audio) < SAMPLE_RATE // 4:
                print("\r too short, hold the key while you speak   ")
                continue
            started = time.time()
            said = ears.transcribe(audio)
            heard_ms = (time.time() - started) * 1000
            if not said:
                print("\r nothing heard   ")
                continue
            print(f'\r heard "{said}"  ({heard_ms:.0f} ms)')
            run = execute(said, adapter, engine, registry, commit=commit, confirm=confirm, on_step=announce)
            print(f"   {run.verdict}\n")
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        adapter.close()
