"""What the machine can do right now, as one indexed list.

Every adapter produces entries of the same shape. The decision model only ever
sees this list and only ever answers with an index off it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verb(str, Enum):
    """The shared vocabulary. A browser and a Mac window both fit in it."""

    PRESS = "PRESS"
    CLICK = "CLICK"
    TYPE_TEXT = "TYPE_TEXT"
    SELECT = "SELECT"
    MENU = "MENU"
    FOCUS_APP = "FOCUS_APP"
    SCROLL_UP = "SCROLL_UP"
    SCROLL_DOWN = "SCROLL_DOWN"
    PRESS_RETURN = "PRESS_RETURN"
    PRESS_ESCAPE = "PRESS_ESCAPE"
    WAIT = "WAIT"
    DONE = "DONE"
    BLOCKED = "BLOCKED"


class Reversibility(int, Enum):
    """How much confidence an entry needs before it may run.

    FREE may fire on a half-finished sentence. UNDOABLE waits for the sentence
    to end. PERMANENT never fires on its own.
    """

    FREE = 0
    UNDOABLE = 1
    PERMANENT = 2


class Tier(str, Enum):
    """How deeply an app was read.

    DEEP is every actionable element. SHALLOW is enough to know the app is
    there and to reach it.
    """

    DEEP = "deep"
    SHALLOW = "shallow"


# Reversibility is a property of the verb and the app, never of the label.
# Labels are written by whoever wrote the window, so a rule that reads them can
# be steered by a button that calls itself something harmless.
VERB_FLOOR: dict[Verb, Reversibility] = {
    Verb.WAIT: Reversibility.FREE,
    Verb.DONE: Reversibility.FREE,
    Verb.BLOCKED: Reversibility.FREE,
    Verb.SCROLL_UP: Reversibility.FREE,
    Verb.SCROLL_DOWN: Reversibility.FREE,
    Verb.PRESS_ESCAPE: Reversibility.FREE,
    Verb.FOCUS_APP: Reversibility.FREE,
    Verb.TYPE_TEXT: Reversibility.UNDOABLE,
    Verb.SELECT: Reversibility.UNDOABLE,
    Verb.PRESS_RETURN: Reversibility.UNDOABLE,
    Verb.MENU: Reversibility.UNDOABLE,
    Verb.PRESS: Reversibility.PERMANENT,
    Verb.CLICK: Reversibility.PERMANENT,
}

# Pressing something is only as safe as the app it happens in, and no reading of
# the button tells you which. An app earns a lower floor by being named here.
APP_PRESS_FLOOR: dict[str, Reversibility] = {
    "Calculator": Reversibility.FREE,
    "Finder": Reversibility.UNDOABLE,
    "Notes": Reversibility.UNDOABLE,
    "TextEdit": Reversibility.UNDOABLE,
    "Preview": Reversibility.UNDOABLE,
    "System Settings": Reversibility.PERMANENT,
}

DEFAULT_PRESS_FLOOR = Reversibility.PERMANENT


def reversibility_of(verb: Verb, app: str) -> Reversibility:
    """The class an entry runs under. Code decides this, nothing observed does."""
    floor = VERB_FLOOR[verb]
    if verb in (Verb.PRESS, Verb.CLICK):
        return APP_PRESS_FLOOR.get(app, DEFAULT_PRESS_FLOOR)
    return floor


@dataclass(frozen=True)
class Entry:
    """One thing that can be done, right now."""

    index: int
    verb: Verb
    label: str
    app: str
    owner: str
    reversibility: Reversibility
    observed_at: float
    tier: Tier = Tier.DEEP
    needs_text: bool = False
    handle: Any = None  # whatever the owning adapter needs to execute it

    def age(self) -> float:
        return time.time() - self.observed_at


@dataclass
class Registry:
    """The merged list, rebuilt continuously rather than on demand."""

    entries: list[Entry] = field(default_factory=list)

    def replace(self, owner: str, app: str, entries: list[Entry]) -> None:
        """Swap one app's contribution without disturbing the others."""
        self.entries = [e for e in self.entries if not (e.owner == owner and e.app == app)]
        self.entries.extend(entries)
        self._reindex()

    def _reindex(self) -> None:
        """Indices are positions in the current list and mean nothing across rebuilds."""
        ordered = sorted(self.entries, key=lambda e: (e.tier is Tier.SHALLOW, e.app, e.label))
        self.entries = [
            Entry(**{**e.__dict__, "index": i}) for i, e in enumerate(ordered)
        ]

    def apps(self) -> list[str]:
        seen: dict[str, None] = {}
        for e in self.entries:
            seen.setdefault(e.app, None)
        return list(seen)

    def narrow(self, app: str | None = None, tier: Tier | None = None) -> list[Entry]:
        """The second question only ever sees what the first one selected."""
        out = self.entries
        if app is not None:
            out = [e for e in out if e.app == app]
        if tier is not None:
            out = [e for e in out if e.tier is tier]
        return out

    def may_speculate(self, entry: Entry) -> bool:
        """Only the free class may run before the sentence is finished."""
        return entry.reversibility is Reversibility.FREE

    def render(self, entries: list[Entry] | None = None, label_chars: int = 60) -> str:
        """The table the model reads. Nothing here is an instruction to it."""
        rows = self.entries if entries is None else entries
        return "\n".join(
            f"{e.index}\t{e.verb.value}\t{e.app}\t{e.label[:label_chars]}" for e in rows
        )
