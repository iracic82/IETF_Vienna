#!/usr/bin/env bash
# Pass if the student called verify_agent_dns on threat-feed AND the
# assistant's most recent answer mentions at least 3 distinct anomaly signals.
set -uo pipefail

EVENTS=$(curl -fsS "http://event-hub:8888/events?since=500" || echo "[]")

result=$(echo "${EVENTS}" | python3 <<'PY'
import json, sys
events = json.load(sys.stdin)

verified_threat_feed = False
recent_text = ""
for e in events:
    if e.get("kind") == "tools_call":
        tool = e.get("tool") or ""
        args = e.get("args") or {}
        if "verify" in tool and "threat-feed" in json.dumps(args):
            verified_threat_feed = True
    if e.get("kind") == "rpc" and e.get("direction") == "response":
        recent_text = e.get("text_preview", "") or recent_text

signals = ["external", "tor", "rogue", "k-d.chen", "no policy", "missing policy",
           "after termination", "publish", "endpoint", "185.234"]
hits = sum(1 for s in signals if s.lower() in recent_text.lower())

print(json.dumps({"verified": verified_threat_feed, "signal_hits": hits}))
PY
)

if echo "${result}" | grep -q '"verified": true' && echo "${result}" | python3 -c '
import json, sys
hits = json.loads(sys.stdin.read())["signal_hits"]
sys.exit(0 if hits >= 3 else 1)
'; then
    echo "✓ rogue identified, signals cited"
    exit 0
fi
echo "✗ either threat-feed not verified yet, or fewer than 3 signals named in the latest answer"
exit 1
