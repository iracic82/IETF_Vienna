#!/usr/bin/env bash
# Fix a broken dns-aid route53.py where _chunk255 helper was prepended
# BEFORE `from __future__ import annotations` (Python syntax error).
# Idempotent: safe to re-run.
set -euo pipefail

R53=$(ls /root/.local/share/uv/tools/dns-aid/lib/python*/site-packages/dns_aid/backends/route53.py 2>/dev/null | head -1)
if [ -z "${R53}" ]; then
    echo "ERROR: route53.py not found — is dns-aid installed?" >&2
    exit 1
fi

python3 <<PY
import re, pathlib
p = pathlib.Path("${R53}")
s = p.read_text()
m = re.search(r'\ndef _chunk255\(s\):.*?return " "\.join.*?\n', s, re.DOTALL)
if not m:
    print("nothing to fix (no _chunk255 helper found)")
    raise SystemExit(0)
helper = m.group(0)
# Remove from current position, re-insert after the future import.
s = s.replace(helper, "", 1)
marker = "from __future__ import annotations\n"
if marker not in s:
    print("ERROR: route53.py has no future-import line — cannot reorder", file=__import__("sys").stderr)
    raise SystemExit(1)
s = s.replace(marker, marker + helper, 1)
p.write_text(s)
print("fixed:", p)
PY

dns-aid --version
