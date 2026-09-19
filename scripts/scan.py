"""Print what the machine can do right now. The registry, with no voice attached."""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.adapters.mac import MacAdapter
from flow.registry import Registry, Reversibility, Tier

adapter = MacAdapter()
registry = Registry()
front = adapter.frontmost()

for app in adapter.apps():
    name = app["name"]
    tier = Tier.DEEP if name == front else Tier.SHALLOW
    registry.replace(adapter.name, name, adapter.scan(name, tier))

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
