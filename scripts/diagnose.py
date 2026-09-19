"""Timings and what the element table is actually made of."""

import collections
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jarvis.adapters.mac import MacAdapter

a = MacAdapter()
front = a.frontmost()

t0 = time.time(); page = a.bridge.call("snapshot", app=front, menus=True, limit=250); t1 = time.time()
print(f"deep read of {front:12} {(t1 - t0) * 1000:6.0f} ms   truncated={page.get('truncated')}")
t0 = time.time(); a.apps(); t1 = time.time()
print(f"app list                  {(t1 - t0) * 1000:6.1f} ms")
t0 = time.time(); a.bridge.call("fingerprint", app=front, limit=250); t1 = time.time()
print(f"freshness check           {(t1 - t0) * 1000:6.0f} ms")

others = [x["name"] for x in a.apps() if x["name"] != front][:4]
for name in others:
    t0 = time.time()
    try:
        p = a.bridge.call("snapshot", app=name, menus=False, limit=250)
        n = len(p.get("elements", []))
    except Exception as error:
        n = f"failed, {str(error)[:40]}"
    print(f"deep read of {name:12} {(time.time() - t0) * 1000:6.0f} ms   elements={n}")

els = page["elements"]
print(f"\nelements {len(els)}   menus {len(page.get('menus', []))}")
pairs = collections.Counter()
for e in els:
    for op in e.get("operations", []):
        pairs[(e.get("role", ""), op)] += 1
print("\nrole x operation, most common")
for (role, op), n in pairs.most_common(14):
    print(f"  {n:4}  {role:24} {op}")
print(f"\nno label at all: {sum(1 for e in els if not (e.get('label') or '').strip())} of {len(els)}")
a.close()
