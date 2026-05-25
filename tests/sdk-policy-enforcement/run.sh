#!/usr/bin/env bash
# Run the SDK policy enforcement test in an isolated venv.
# Idempotent: skips dns-aid install if already present.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="${HERE}/.venv"

if [ ! -d "${VENV}" ]; then
    echo "[test] creating venv at ${VENV}"
    python3 -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

# Install dns-aid SDK (only the bits we need: SDK + policy).
if ! python3 -c "import dns_aid.sdk.policy.evaluator" 2>/dev/null; then
    echo "[test] installing dns-aid + dependencies"
    pip install --quiet --upgrade pip
    pip install --quiet "dns-aid[mcp,cel]>=0.21.0"
fi

echo "[test] dns-aid version:"
python3 -c "import dns_aid; print('  ', dns_aid.__version__)"

echo ""
echo "[test] running test_guard.py"
echo "────────────────────────────────────────────────────────────────"
python3 "${HERE}/test_guard.py"
