"""What every surface has to provide to contribute to the registry.

An adapter owns observation and execution for one kind of surface. Nothing
above it knows how to press anything.
"""

from __future__ import annotations

from typing import Protocol

from flow.registry import Entry, Tier


class Adapter(Protocol):
    name: str

    def targets(self) -> list[str]:
        """The things this adapter can read, one name per app, page or service."""

    def scan(self, target: str, tier: Tier) -> list[Entry]:
        """What is possible in that target right now."""

    def fresh(self, entry: Entry) -> bool:
        """Is the world still the one this entry was observed in?"""

    def execute(self, entry: Entry, text: str | None = None) -> dict:
        """Carry it out. Refuses rather than acting on a target that moved."""
