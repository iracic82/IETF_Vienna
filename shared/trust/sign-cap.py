"""Sign a cap document with one of the demo keys.

Usage:
    python sign-cap.py --key k-ops-team-2026 --in cap.json --out cap.json.jws

The output is a compact JWS (header.payload.signature). The cap document
URL referenced from SVCB key65400 should serve the JWS string (or a JSON
envelope containing both raw payload and signature, per Pattern A in the
existing integration docs).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jwcrypto import jwk, jws

HERE = Path(__file__).parent
KEYS_DIR = HERE / "keys"


def sign(payload: bytes, kid: str) -> str:
    pem_path = KEYS_DIR / f"{kid}.pem"
    if not pem_path.exists():
        sys.exit(f"key not found: {pem_path} — run generate-keys.py first")

    key = jwk.JWK.from_pem(pem_path.read_bytes())
    token = jws.JWS(payload)
    token.add_signature(
        key,
        alg="RS256",
        protected={"alg": "RS256", "kid": kid, "typ": "dns-aid-cap+jws"},
    )
    return token.serialize(compact=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--key", required=True, help="kid, e.g. k-ops-team-2026")
    p.add_argument("--in", dest="inp", required=True, help="cap JSON path")
    p.add_argument("--out", required=True, help="output JWS path")
    args = p.parse_args()

    payload = Path(args.inp).read_bytes()
    token = sign(payload, args.key)
    Path(args.out).write_text(token)
    print(f"signed {args.inp} → {args.out} with {args.key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
