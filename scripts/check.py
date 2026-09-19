"""Is the decision route actually usable? Prints why not, when not."""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flow.decide import PROFILES, HostedEngine

try:
    engine = HostedEngine()
except RuntimeError as error:
    sys.exit(str(error))

print(f"route      {engine.profile}")
print(f"model      {engine.model}")
print(f"key        loaded, {len(engine.key)} characters")

if engine.profile == "vercel":
    request = urllib.request.Request(
        "https://ai-gateway.vercel.sh/v1/credits",
        headers={"Authorization": f"Bearer {engine.key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            credits = json.loads(response.read())
        print(f"credits    {credits.get('balance')} available, {credits.get('total_used')} used")
    except urllib.error.HTTPError as error:
        print(f"credits    unavailable, {error.code}")

try:
    decision = engine.ask(
        {"note": "a readiness check"},
        {"ready": {"type": "boolean", "instructions": "Is this a readiness check?"}},
    )
except RuntimeError as error:
    message = str(error)
    print(f"\nnot usable yet\n{message[:200]}")
    if "credit card" in message:
        print(
            "\nThe key is valid and the credits are there. Gateway keys belong to one\n"
            "Vercel team, so the card has to be on that same team. Check the team\n"
            "switcher on the AI Gateway page against the team the key was made in."
        )
    sys.exit(1)

answer = decision.answers["ready"]
print(f"\nworking    {decision.latency_ms} ms, answered {answer.choice} at {answer.confidence:.2f}")
print(f"usage      {decision.usage}")
