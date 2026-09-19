"""Say what you want in words, watch it happen. No voice yet, type it instead.

    python3 scripts/do.py "go back"
    python3 scripts/do.py --go "open settings"

Without --go nothing runs, it only reports what it would have done.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.decide import engine as make_engine, questions_for, state_for
from flow.registry import Registry, Reversibility, Tier

args = [a for a in sys.argv[1:] if a != "--go"]
commit = "--go" in sys.argv
if not args:
    sys.exit(__doc__)
goal = " ".join(args)

adapter = MacAdapter()
engine = make_engine()
registry = Registry()

started = time.time()
front = adapter.frontmost()
for app in adapter.apps():
    name = app["name"]
    registry.replace(adapter.name, name, adapter.scan(name, Tier.DEEP if name == front else Tier.SHALLOW))
read_ms = (time.time() - started) * 1000

# Narrowing by app first cost more than it bought. Asking a small model which
# of sixteen apps a goal is about puts the right answer out of reach whenever it
# guesses wrong, and the word shortlist already spans every app.
candidates = registry.entries
if len(candidates) > engine.max_options:
    candidates = registry.shortlist(goal, candidates, engine.max_options)

decision = engine.ask(state_for(registry, candidates, front), questions_for(goal, candidates))
action = decision.answers["action"]
addressed = decision.answers.get("addressed")
chosen = next((e for e in candidates if str(e.index) == action.choice), None)

print(f'goal        "{goal}"')
print(f"read        {read_ms:.0f} ms, {len(registry.entries)} entries across {len(registry.apps())} apps")
if len(candidates) < len(registry.entries):
    print(f"shortlist   {len(candidates)} candidates from {len(registry.entries)}")
print(f"decided     {decision.latency_ms} ms on the {engine.profile} route")
if addressed:
    print(f"a command   {addressed.probabilities.get('true', 0):.2f}")
if chosen is None:
    sys.exit(f"chose {action.choice!r}, which is not on the list. Nothing ran.")
print(f"chose       {chosen.verb.value} \"{chosen.label}\" in {chosen.app}")
print(f"confidence  {action.confidence:.2f}   class {chosen.reversibility.name}")

if not commit:
    print("\nnothing ran, pass --go to let it act")
elif chosen.reversibility is Reversibility.FREE:
    print("\nfree, running it")
    print(adapter.execute(chosen))
else:
    answer = input(f"\n{chosen.reversibility.name.lower()}, run it? [y/N] ")
    if answer.strip().lower() == "y":
        print(adapter.execute(chosen))
    else:
        print("left alone")
adapter.close()
