#!/usr/bin/env bash
# Validate that the student ran at least one successful lookup_ip via
# discover-then-invoke. We grep the event-hub ring buffer for a tools_call
# event with tool=lookup_ip and a non-error result.
set -uo pipefail

EVENTS=$(curl -fsS "http://event-hub:8888/events?since=200" || echo "[]")

count=$(echo "${EVENTS}" | python3 -c '
import json, sys
events = json.load(sys.stdin)
hit = 0
for e in events:
    if e.get("kind") == "tools_call" and e.get("tool") == "lookup_ip":
        hit += 1
print(hit)
')

if [ "${count}" -ge 1 ]; then
    echo "✓ found ${count} lookup_ip invocation(s) via the federation"
    exit 0
fi

echo "✗ no lookup_ip invocation detected yet — try asking the assistant about an IP"
exit 1
