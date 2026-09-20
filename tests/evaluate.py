"""Score the decision layer against a saved registry.

Reports the two failure modes separately. A miss in the shortlist is a scoring
problem and nothing downstream can recover it. A miss after that is the model
choosing badly from a list that held the answer.

    .venv/bin/python tests/evaluate.py
    .venv/bin/python tests/evaluate.py --shortlist-only
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flow.registry import Entry, Registry, Reversibility, Tier, Verb
from tests.goals import GOALS, JUNK

FIXTURE = ROOT / "tests" / "fixtures" / "registry.json"
if not FIXTURE.exists():
    sys.exit("No saved registry. Run: .venv/bin/python scripts/scan.py --dump")

saved = json.loads(FIXTURE.read_text())
registry = Registry()
registry.entries = [
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
    )
    for e in saved["entries"]
]
frontmost = saved["frontmost"]
shortlist_only = "--shortlist-only" in sys.argv

if not shortlist_only:
    from flow.decide import DECLINE, engine as make_engine, questions_for, state_for

    engine = make_engine()
    limit = engine.max_options
else:
    engine = None
    limit = 20

print(f"{len(registry.entries)} entries, frontmost {frontmost}, shortlist of {limit}\n")

in_list = picked = 0
confident_right = confident_wrong = 0
THRESHOLD = getattr(engine, 'threshold', 0.8) if engine else 0.8
rows = []

for goal, expected in GOALS:
    present = [e for e in registry.entries if expected.lower() in e.label.lower()]
    if not present:
        rows.append((goal, "absent", "", 0.0))
        continue
    short = registry.shortlist(goal, registry.entries, limit)
    hit = any(expected.lower() in e.label.lower() for e in short)
    in_list += hit
    if shortlist_only:
        rank = next((i for i, e in enumerate(short) if expected.lower() in e.label.lower()), None)
        rows.append((goal, "in" if hit else "MISSED", f"rank {rank}" if hit else "", 0.0))
        continue

    decision = engine.ask(state_for(goal), questions_for(goal, short))
    answer = decision.answers["action"]
    chosen = next((e for e in short if str(e.index) == answer.choice), None)
    if answer.choice == DECLINE:
        rows.append((goal, "declined", "nothing matched", answer.confidence))
        continue
    right = chosen is not None and expected.lower() in chosen.label.lower()
    picked += right
    if answer.confidence >= THRESHOLD:
        confident_right += right
        confident_wrong += not right
    rows.append((goal, "ok" if right else "wrong", (chosen.label if chosen else "?")[:34], answer.confidence))

width = max(len(g) for g, *_ in rows)
for goal, verdict, detail, confidence in rows:
    mark = {"ok": "  ", "in": "  ", "absent": " -", "declined": " ?", "MISSED": " X", "wrong": " X"}[verdict]
    print(f"{mark} {goal:{width}}  {verdict:7} {confidence:.2f}  {detail}")

if not shortlist_only:
    declined = 0
    for goal in JUNK:
        short = registry.shortlist(goal, registry.entries, limit)
        answer = engine.ask(state_for(goal), questions_for(goal, short)).answers["action"]
        declined += answer.choice == DECLINE
    print(f"\nnonsense            {len(JUNK)} requests, {declined} declined outright")

usable = [g for g, e in GOALS if any(e.lower() in x.label.lower() for x in registry.entries)]
print(f"\ntestable            {len(usable)} of {len(GOALS)}")
print(f"answer in shortlist {in_list}/{len(usable)}")
if not shortlist_only:
    print(f"model picked it     {picked}/{len(usable)}")
    acted = confident_right + confident_wrong
    print(f"above {THRESHOLD:.0%} confidence  {acted} would act, {confident_right} right, {confident_wrong} wrong")
