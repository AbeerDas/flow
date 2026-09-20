"""Print what the machine can do right now. The registry, with no voice attached."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.registry import Registry, Reversibility, Tier
from flow.run import observe

adapter = MacAdapter()
registry = Registry()
# The same read the real thing does, so a saved registry matches what runs.
front = observe(adapter, registry)

deep = registry.narrow(tier=Tier.DEEP)
shallow = registry.narrow(tier=Tier.SHALLOW)
classes = Counter(e.reversibility.name for e in registry.entries)

print(f"frontmost      {front}")
print(f"apps           {len(registry.apps())}")
print(f"entries        {len(registry.entries)}  ({len(deep)} deep, {len(shallow)} shallow)")
print(f"by class       {dict(classes)}")
print(f"may speculate  {sum(1 for e in registry.entries if registry.may_speculate(e))}")
print()
print(registry.render(deep[:25]))
adapter.close()

# A saved registry lets the decision layer be worked on without accessibility
# permission, which the shell running the tests does not have.
if "--dump" in sys.argv:
    import json

    out = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "registry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "frontmost": front,
                "entries": [
                    {
                        "index": e.index,
                        "verb": e.verb.value,
                        "label": e.label,
                        "app": e.app,
                        "owner": e.owner,
                        "reversibility": e.reversibility.value,
                        "observed_at": e.observed_at,
                        "tier": e.tier.value,
                        "needs_text": e.needs_text,
                    }
                    for e in registry.entries
                ],
            },
            indent=1,
        )
    )
    print(f"\nwrote {out} with {len(registry.entries)} entries")
