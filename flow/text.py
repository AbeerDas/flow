"""The words to type, taken from what was said rather than written fresh.

The decision model cannot generate text. It does not have to: when someone says
"make a note saying pick up milk", the words to type are already in the
sentence. Code proposes the spans and the model picks one, so nothing is
invented and nothing needs a second model.
"""

from __future__ import annotations

import re

# What usually stands between the instruction and the words meant for the app.
MARKERS = (
    "saying",
    "that says",
    "which says",
    "titled",
    "called",
    "named",
    "with the text",
    "write",
    "type",
    "say",
)

QUOTED = re.compile(r"[\"'“‘]([^\"'”’]{2,})[\"'”’]")


def spans(goal: str) -> list[str]:
    """Candidate strings to type, best first, never more than a handful."""
    found: list[str] = []

    for match in QUOTED.finditer(goal):
        found.append(match.group(1).strip())

    # Whole words only, longest first, so "say" does not cut "saying" in half.
    for marker in sorted(MARKERS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(marker)}\b", goal, re.IGNORECASE)
        if match:
            tail = goal[match.end() :].strip(" ,:")
            if tail:
                found.append(tail)

    found.append(goal)

    seen: set[str] = set()
    unique = []
    for candidate in found:
        cleaned = candidate.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique.append(cleaned)
    return unique[:5]


def wants_text(goal: str) -> bool:
    """Does the request ask for something to be typed?

    A marker with words after it is the signal. "Write" alone is a verb about
    an app; "write pick up milk" carries its own payload.
    """
    for marker in sorted(MARKERS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(marker)}\b", goal, re.IGNORECASE)
        if match and goal[match.end() :].strip(" ,:."):
            return True
    return bool(QUOTED.search(goal))


# Joins that separate two instructions rather than two things in one.
SPLITS = re.compile(r"\b(?:and then|then|and)\b", re.IGNORECASE)


def clauses(goal: str) -> list[str]:
    """One request, split where it holds two instructions.

    "Open notes and write pick up milk" is two things, and asked as one the
    model declines rather than choosing a half. Splitting is code's job: the
    join is in the sentence, not in the meaning.

    A join inside the words meant for typing is left alone, since "buy eggs
    and bread" is one thing.
    """
    head = goal
    payload = ""
    for marker in sorted(MARKERS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(marker)}\b", goal, re.IGNORECASE)
        if match and goal[match.end() :].strip(" ,:."):
            head, payload = goal[: match.start()], goal[match.start() :]
            break

    parts = [p.strip(" ,.") for p in SPLITS.split(head)]
    parts = [p for p in parts if p]
    if payload.strip():
        parts.append(payload.strip(" ,."))
    return parts or [goal]
