"""Say what you want in words, watch it happen. No voice yet, type it instead.

    python3 scripts/do.py "go back"
    python3 scripts/do.py --go "open notes and write buy milk"

Without --go nothing runs, it only reports the first thing it would have done.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.decide import describe, engine as make_engine
from flow.registry import Registry
from flow.run import execute

args = [a for a in sys.argv[1:] if not a.startswith("--")]
commit = "--go" in sys.argv
if not args:
    sys.exit(__doc__)
goal = " ".join(args)


def confirm(entry, confidence, text):
    detail = f' with "{text}"' if text else ""
    prompt = f"  {entry.reversibility.name.lower()}, {describe(entry)}{detail} at {confidence:.2f}. run it? [y/N] "
    return input(prompt).strip().lower() == "y"


def announce(step):
    detail = f' with "{step.text}"' if step.text else ""
    print(f"  {step.confidence:.2f}  {describe(step.entry)}{detail}")


adapter = MacAdapter()
engine = make_engine()
registry = Registry()

print(f'goal        "{goal}"')
started = time.time()
run = execute(goal, adapter, engine, registry, commit=commit, confirm=confirm, on_step=announce)
print(f"\n{run.verdict} in {time.time() - started:.1f}s, {len(run.steps)} step(s) on the {engine.profile} route")
for i, step in enumerate(run.steps, 1):
    print(f"  {i}. {step.outcome}")
if not commit:
    print("\nnothing ran, pass --go to let it act")
adapter.close()
