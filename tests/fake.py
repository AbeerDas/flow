"""An adapter that serves a saved registry, so the loop can be tested anywhere.

Accessibility is granted to the interactive shell and not to the one running
the tests. This stands in for the machine: reads answer from the snapshot, and
executing records what would have happened rather than doing it.
"""

import json
from pathlib import Path

from flow.registry import Entry, Reversibility, Tier, Verb

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "registry.json"


class FakeAdapter:
    name = "mac"

    def __init__(self, fixture: Path = FIXTURE):
        saved = json.loads(fixture.read_text())
        self.front = saved["frontmost"]
        self.performed: list[str] = []
        self._entries = [
            Entry(
                index=e["index"],
                verb=Verb(e["verb"]),
                label=e["label"],
                app=e["app"],
                owner=e["owner"],
                reversibility=Reversibility(e["reversibility"]),
                observed_at=e["observed_at"],
                tier=Tier(e["tier"]),
                needs_text=e["needs_text"],
                handle={"kind": "fake"},
            )
            for e in saved["entries"]
        ]

    def apps(self):
        names = []
        for entry in self._entries:
            if entry.app not in names:
                names.append(entry.app)
        return [{"name": n, "frontmost": n == self.front} for n in names]

    def frontmost(self):
        return self.front

    def scan(self, target, tier=Tier.DEEP):
        return [e for e in self._entries if e.app == target and e.tier is tier]

    def execute(self, entry, text=None):
        self.performed.append(entry.label + (f' <- "{text}"' if text else ""))
        return {"ok": True}

    def close(self):
        pass
