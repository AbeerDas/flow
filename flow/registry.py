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
    LAUNCH_APP = "LAUNCH_APP"
    SEARCH_WEB = "SEARCH_WEB"
    OPEN_URL = "OPEN_URL"
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
    Verb.LAUNCH_APP: Reversibility.FREE,
    Verb.SEARCH_WEB: Reversibility.FREE,
    Verb.OPEN_URL: Reversibility.FREE,
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


# Below this the model starts declining instead of choosing.
MIN_CANDIDATES = 5

COMMAND_VERBS = {Verb.MENU, Verb.FOCUS_APP, Verb.LAUNCH_APP, Verb.SEARCH_WEB, Verb.OPEN_URL}

# People ask for things by a different word than the menu uses. "Add another
# note" lost File>New Note to "Undo Add Note", which matched two of the spoken
# words against one, and the right answer never reached the model.
SYNONYMS = {
    "add": {"new", "create"},
    "create": {"new", "add"},
    "make": {"new", "create"},
    "new": {"add", "create"},
    "another": {"new"},
    "search": {"find"},
    "find": {"search"},
    "look": {"find", "search"},
    # A tab or a window is closed, not deleted, but people say both.
    "delete": {"remove", "trash", "close"},
    "remove": {"delete", "trash", "close"},
    "close": {"delete", "quit"},
    "quit": {"close", "exit"},
    "shut": {"close", "quit"},
    "type": {"write", "enter"},
    "write": {"type", "enter"},
    "enter": {"type", "write"},
    "go": {"open", "switch"},
    "switch": {"open", "go"},
    "bring": {"switch", "open"},
    "tab": {"window"},
    "undo": {"revert"},
}

STOPWORDS = {"the", "a", "an", "to", "in", "on", "my", "me", "please", "and", "of", "for", "it"}


def _names(app: str, wanted: list[str]) -> bool:
    """Was this app named? Any distinctive word of it is enough.

    Requiring the whole name meant "chrome" never matched "Google Chrome".
    """
    return any(w in wanted for w in _words(app) if len(w) >= 4)


def _words(text: str) -> list[str]:
    return [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if w]


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

    def replace_all(self, owner: str, entries: list[Entry]) -> None:
        """Swap everything one source contributed, across every app it covers."""
        self.entries = [e for e in self.entries if e.owner != owner]
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

    def shortlist(self, goal: str, entries: list[Entry] | None = None, limit: int = 20) -> list[Entry]:
        """The most plausible few, by word overlap alone.

        Narrowing to one app is not enough when that app is the whole list, and
        a small model shown two hundred options answers confidently from the
        wrong part of them. This costs nothing and runs before the model sees
        anything. What it drops the model can never choose, so it ranks every
        entry the same way rather than reserving room for any kind.

        The app name counts as part of the text, so "quit claude" reaches
        Claude's own menu without anything having to say which app that is.
        """
        rows = self.entries if entries is None else entries
        wanted = [w for w in _words(goal) if w not in STOPWORDS]
        if not wanted:
            return rows[:limit]

        def score(entry: Entry) -> tuple:  # noqa: C901
            app = set(_words(entry.app))
            text = set(_words(entry.label)) | app
            covered = sum(1 for w in wanted if w in text or (SYNONYMS.get(w, set()) & text))
            # Naming an app is a much stronger signal than sharing a word with
            # a control. "Open a new tab in chrome" matched a button called
            # "Open in new window" on two words and lost Chrome, which it had
            # named outright.
            # Any distinctive word of the name is enough. Requiring all of
            # them meant "chrome" never matched "Google Chrome".
            named = 1 if _names(entry.app, wanted) else 0
            # A menu item or an app is a named command. A button carrying a
            # pull request title is content that happens to be clickable, and
            # a window full of it otherwise wins on sharing one common word.
            command = 1 if entry.verb in COMMAND_VERBS else 0
            return (named, covered / len(wanted), command, covered, -len(entry.label))

        # Every installed app is launchable, which is 84 options that are only
        # ever relevant when the app is named. Left in, nonsense requests found
        # somewhere to land and declining fell from 7 of 7 to 5 of 7.
        rows = [e for e in rows if e.verb is not Verb.LAUNCH_APP or _names(e.app, wanted)]

        # Naming an app scopes the request to it. Ranking alone was not enough:
        # "open notes" put the Notes app first and the model still preferred a
        # button labelled with a pull request title, because that button was on
        # the list at all. Naming an app takes the others off it.
        named_apps = {e.app for e in rows if _names(e.app, wanted)}
        if named_apps:
            scoped = [e for e in rows if e.app in named_apps]
            # Scoping to one app can leave a single option, and this model
            # declines rather than choosing when the list is that short. Keep
            # the named app's entries first and fill the rest behind them.
            if len(scoped) < MIN_CANDIDATES:
                # Pad with named commands only. Padding with whatever ranked
                # next brought back the buttons carrying page text, and "open
                # safari" went to one of them again.
                rest = [
                    e for e in rows
                    if e.app not in named_apps and e.verb in COMMAND_VERBS
                ]
                rows = scoped + sorted(rest, key=score, reverse=True)
            else:
                rows = scoped
        ranked = sorted(rows, key=score, reverse=True)
        # A window can offer the same control several times over, and three
        # identical lines give one option three times the surface area without
        # adding a choice.
        seen: set[tuple] = set()
        unique = []
        for entry in ranked:
            key = (entry.verb, entry.label, entry.app)
            if key not in seen:
                seen.add(key)
                unique.append(entry)
            if len(unique) == limit:
                break
        return unique

    def may_speculate(self, entry: Entry) -> bool:
        """Only the free class may run before the sentence is finished."""
        return entry.reversibility is Reversibility.FREE

    def render(self, entries: list[Entry] | None = None, label_chars: int = 60) -> str:
        """The table the model reads. Nothing here is an instruction to it."""
        rows = self.entries if entries is None else entries
        return "\n".join(
            f"{e.index}\t{e.verb.value}\t{e.app}\t{e.label[:label_chars]}" for e in rows
        )
