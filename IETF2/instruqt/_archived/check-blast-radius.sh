#!/usr/bin/env bash
set -uo pipefail

EVENTS=$(curl -fsS "http://event-hub:8888/events?since=500" || echo "[]")

echo "${EVENTS}" | python3 <<'PY'
import json, sys
events = json.load(sys.stdin)

ip_restored = False
key_revoked = False
for e in events:
    if e.get("kind") == "tools_call":
        tool = e.get("tool") or ""
        args = json.dumps(e.get("args") or {})
        if "publish_agent" in tool and "ip-reputation" in args and "k-ops-team-2026" in args:
            ip_restored = True
        if ("publish_rpz" in tool or "compile_policy" in tool) and "k-d.chen-2026" in args:
            key_revoked = True

ok = ip_restored and key_revoked
print("ip-reputation restored:", ip_restored)
print("k-d.chen-2026 key blocked:", key_revoked)
sys.exit(0 if ok else 1)
PY
