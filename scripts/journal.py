"""Read back the last session. Human first, whole rows on request.

    .venv/bin/python scripts/journal.py           # what happened
    .venv/bin/python scripts/journal.py --misses  # only what matched nothing
    .venv/bin/python scripts/journal.py --raw     # every row, as written
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.journal import DEFAULT

path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT
if not path.exists():
    sys.exit(f"no journal at {path}. Run the listener first.")

rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
if "--raw" in sys.argv:
    for row in rows:
        print(json.dumps(row))
    sys.exit(0)

misses_only = "--misses" in sys.argv
for row in rows:
    kind = row["kind"]
    at = row["at"]
    if kind == "heard" and not misses_only:
        print(f'\n[{at:7.1f}s] heard "{row["said"]}"')
    elif kind == "observed" and not misses_only:
        print(f"           saw {row['entries']} things, {row['frontmost']} in front")
    elif kind == "decided":
        matched = row["chose"] not in ("none", "done")
        if misses_only and matched:
            continue
        if misses_only:
            print(f'\n[{at:7.1f}s] "{row["clause"]}" -> {row["chose"]}')
        print(f"           chose {row['chose']} at {row['confidence']:.2f}"
              f"  (decline {row['p_decline']:.2f}, done {row['p_done']:.2f})")
        for option in row["options"]:
            mark = ">" if str(option["index"]) == row["chose"] else " "
            print(f"           {mark} {option['p']:.2f} [{option['class'][:4]}] {option['says'][:62]}")
    elif kind == "action_failed":
        print(f"           FAILED {row['label'][:40]}: {row['error'][:70]}")
    elif kind == "finished" and not misses_only:
        print(f"           -> {row['verdict']}")
