"""Generate the two demo signing keys for the IETF_Vienna labs.

Produces:
    keys/k-ops-team-2026.pem            RSA-2048 private key (legit signer)
    keys/k-d.chen-2026.pem              RSA-2048 private key (compromised)
    jwks.json                            public JWKS containing both kids

These are LAB KEYS, not production secrets. They are intentionally
committed to the repo so every learner's sandbox can verify cap-doc
signatures without per-sandbox key generation. The story is that
k-d.chen-2026 was the personal signing key of a terminated employee whose
key revocation hasn't completed yet — exactly the IETF2 scenario.

Run once from this directory:
    python generate-keys.py

Idempotent — if keys exist, prints their fingerprints and exits.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwcrypto import jwk

KEY_IDS = ["k-ops-team-2026", "k-d.chen-2026"]
HERE = Path(__file__).parent
KEYS_DIR = HERE / "keys"
JWKS_PATH = HERE / "jwks.json"


def make_rsa_pem(path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)


def jwk_from_pem(path: Path, kid: str) -> dict:
    pem = path.read_bytes()
    key = jwk.JWK.from_pem(pem)
    pub = json.loads(key.export_public())
    pub["kid"] = kid
    pub["use"] = "sig"
    pub["alg"] = "RS256"
    return pub


def main() -> int:
    KEYS_DIR.mkdir(exist_ok=True)
    created = []
    for kid in KEY_IDS:
        pem_path = KEYS_DIR / f"{kid}.pem"
        if pem_path.exists():
            print(f"  exists: {pem_path}")
        else:
            make_rsa_pem(pem_path)
            created.append(kid)
            print(f"  created: {pem_path}")

    jwks = {"keys": [jwk_from_pem(KEYS_DIR / f"{kid}.pem", kid) for kid in KEY_IDS]}
    JWKS_PATH.write_text(json.dumps(jwks, indent=2))
    print(f"  wrote:   {JWKS_PATH}  ({len(jwks['keys'])} keys)")

    if created:
        print("\nNew keys generated. Commit the .pem files AND jwks.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
