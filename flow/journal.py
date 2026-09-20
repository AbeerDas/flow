"""A full record of a session, written where it can be read afterwards.

The console shows a person what happened. This shows everything: what the
machine offered, what the model thought of each option, what was chosen and
what came back. A miss is only diagnosable with the list it was choosing from.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / ".flow-session.jsonl"


class Journal:
    def __init__(self, path: Path | str | None = None, enabled: bool = True):
        self.path = Path(path or os.environ.get("FLOW_JOURNAL", DEFAULT))
        self.enabled = enabled
        self.lock = threading.Lock()
        self.started = time.time()

    def write(self, kind: str, **fields) -> None:
        if not self.enabled:
            return
        row = {"at": round(time.time() - self.started, 3), "kind": kind, **fields}
        line = json.dumps(row, default=str)
        with self.lock:
            with self.path.open("a") as handle:
                handle.write(line + "\n")

    def fresh(self) -> None:
        """Start a new file, so a session is never read mixed with the last one."""
        if self.enabled:
            self.path.write_text("")
            self.write("session", note="started")


# One per process. Nothing here is worth threading through every call.
journal = Journal()
