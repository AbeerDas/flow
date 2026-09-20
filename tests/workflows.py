"""Walk common requests end to end, doing only the harmless parts.

Switching apps really happens, because otherwise a request that spans two apps
cannot get past its first step. Typing and pressing are reported rather than
done, so the whole sequence is visible without anything changing.

    .venv/bin/python tests/workflows.py          # harmless steps only
    .venv/bin/python tests/workflows.py --go     # let it act, asks before risk
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.decide import describe, engine as make_engine
from flow.registry import Registry, Reversibility
from flow.run import execute

WORKFLOWS = [
    "open notes",
    "open notes and write pick up milk",
    "open a new tab in chrome",
    "switch to spotify and pause it",
    "open finder",
    "go back",
    "select all",
    "make a new note saying call the plumber",
    "find in this page",
    "close this window",
    "what is the weather in paris",
]

commit = "--go" in sys.argv
adapter = MacAdapter()
engine = make_engine()
registry = Registry()


def confirm(entry, confidence, text):
    detail = f' with "{text}"' if text else ""
    return input(f"     run {describe(entry)}{detail}? [y/N] ").strip().lower() == "y"


print(f"{'acting, will ask before anything risky' if commit else 'harmless steps only'}\n")
for goal in WORKFLOWS:
    started = time.time()
    run = execute(
        goal,
        adapter,
        engine,
        registry,
        commit=True,
        ceiling=Reversibility.PERMANENT if commit else Reversibility.FREE,
        confirm=confirm,
    )
    print(f'"{goal}"  ->  {run.verdict}, {time.time() - started:.1f}s')
    for i, step in enumerate(run.steps, 1):
        print(f"   {i}. {step.outcome}")
    if not run.steps:
        print("   (no steps)")
    print()
adapter.close()
