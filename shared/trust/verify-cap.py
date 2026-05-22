"""Verify a JWS-signed cap document against the demo JWKS set.

Usage:
    python verify-cap.py --in cap.json.jws

Prints the signer kid and a one-line OK/FAIL.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jwcrypto import jwk, jws

HERE = Path(__file__).parent
JWKS_PATH = HERE / "jwks.json"


def verify(token: str) -> tuple[bool, str | None, dict | None]:
    jwks_doc = json.loads(JWKS_PATH.read_text())
    key_set = jwk.JWKSet.from_json(json.dumps(jwks_doc))

    token_obj = jws.JWS()
    token_obj.deserialize(token)

    header = json.loads(token_obj.objects["protected"]) if isinstance(token_obj.objects.get("protected"), str) else None
    if not header:
        # compact form: header is base64url at index 0
        import base64

        first = token.split(".", 1)[0]
        header = json.loads(base64.urlsafe_b64decode(first + "==").decode())

    kid = header.get("kid")
    if not kid:
        return False, None, None

    matching = key_set.get_key(kid)
    if not matching:
        return False, kid, None

    try:
        token_obj.verify(matching)
    except Exception:
        return False, kid, None

    return True, kid, json.loads(token_obj.payload)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    args = p.parse_args()

    token = Path(args.inp).read_text().strip()
    ok, kid, payload = verify(token)
    if ok:
        print(f"OK   signer={kid} agent={payload.get('agent')}")
        return 0
    else:
        print(f"FAIL signer={kid or 'unknown'}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
