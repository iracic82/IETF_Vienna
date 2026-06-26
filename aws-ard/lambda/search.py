"""AWS Lambda — ARD §7 search API for the IETF Vienna lab.

Routes (via API Gateway HTTP API):
  GET  /                       — health/banner
  POST /search                 — query the GLOBAL catalog (8 reference agents)
  POST /students/{slug}/search — query a PER-STUDENT catalog
  GET  /catalog                — return the raw global catalog
  GET  /students/{slug}/catalog — return the raw per-student catalog

Query envelope (per ARD §7.1):
  {
    "query": {
      "text":   "ip reputation lookup",
      "filter": {"tags": ["threat-intel"], "type": ["application/mcp-server+json"]}
    },
    "federation": "none" | "auto" | "referrals"
  }

Filter semantics (§7.1):
  - Field paths are dot-separated to address nested fields
    (e.g. "trustManifest.attestations.type")
  - Within a single key, values are OR (match-any)
  - Across keys, values are AND
  - When the value at a path is an array, a constraint matches if any
    element satisfies it

Text scoring: simple token-overlap (overlapping_tokens / query_tokens * 100).
Real federations would use BM25/embeddings; this is enough for a workshop.

Catalogs are fetched from S3 per request. They're tiny (<25KB).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

S3 = boto3.client("s3")
BUCKET = os.environ.get("ARD_CATALOG_BUCKET", "ietf-vienna-cap-docs")
GLOBAL_CATALOG_KEY = ".well-known/ai-catalog.json"
PER_STUDENT_PREFIX = "students"


# ─────────────────────────────────────────────────────────────────────
# Catalog fetch
# ─────────────────────────────────────────────────────────────────────


def _catalog_key_for(slug: str | None) -> str:
    if slug is None:
        return GLOBAL_CATALOG_KEY
    return f"{PER_STUDENT_PREFIX}/{slug}/.well-known/ai-catalog.json"


def _derive_student_catalog(slug: str, global_catalog: dict[str, Any]) -> dict[str, Any]:
    """Mint a per-student catalog from the global one by rewriting
    host + per-entry identifier + per-entry trustManifest.identity to
    anchor under the student's sandbox namespace
    (urn:air:<slug>.lab.ccdesanity.com:...).

    This eliminates the need for the lab to ever PUT objects on S3 —
    the lab's scoped AWS creds (Route 53 only) would 'AccessDenied'
    on bucket writes anyway.
    """
    import copy
    derived = copy.deepcopy(global_catalog)

    sandbox_domain = f"{slug}.lab.ccdesanity.com"
    derived["host"] = {
        "displayName":      f"Sandbox {slug} — student federation",
        "identifier":       f"did:web:{sandbox_domain}",
        "documentationUrl": "https://dns-aid.org",
    }

    for entry in derived.get("entries", []):
        # urn:air:lab.ccdesanity.com:agent:<name>
        # → urn:air:<slug>.lab.ccdesanity.com:agent:<name>
        ident = entry.get("identifier", "")
        if ":agent:" in ident:
            name = ident.rsplit(":", 1)[-1]
            entry["identifier"] = f"urn:air:{sandbox_domain}:agent:{name}"
        # Rebrand the publisher object to the student's sandbox.
        if isinstance(entry.get("publisher"), dict):
            entry["publisher"]["identifier"]  = f"did:web:{sandbox_domain}"
            entry["publisher"]["displayName"] = f"Sandbox {slug}"
        # Rewrite trustManifest.identity SPIFFE path to align with new namespace.
        tm = entry.get("trustManifest")
        if isinstance(tm, dict) and tm.get("identity", "").startswith("spiffe://"):
            name = tm["identity"].rsplit("/", 1)[-1]
            tm["identity"] = f"spiffe://{sandbox_domain}/agents/{name}"

    return derived


def _fetch_catalog(slug: str | None) -> dict[str, Any] | None:
    """Return the catalog for the given slug, or None if neither
    persisted (S3) nor derivable (global missing).

    Lookup order:
      1. If S3 has a published catalog at the slug's path → return it.
         (Future: when the lab gets S3-write creds, students publish
         their own entries to this path.)
      2. Otherwise (slug != None) → derive from global catalog.
      3. global catalog itself (slug == None) → return as-is.
    """
    try:
        obj = S3.get_object(Bucket=BUCKET, Key=_catalog_key_for(slug))
        return json.loads(obj["Body"].read())
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("NoSuchKey", "NotFound", "404", "AccessDenied", "Forbidden"):
            raise
        # Fall through to derive-from-global

    if slug is None:
        return None  # global itself is missing — caller will 404

    # Derive on the fly from the global catalog.
    try:
        global_obj = S3.get_object(Bucket=BUCKET, Key=GLOBAL_CATALOG_KEY)
        global_catalog = json.loads(global_obj["Body"].read())
    except ClientError:
        return None
    return _derive_student_catalog(slug, global_catalog)


# ─────────────────────────────────────────────────────────────────────
# Matching
# ─────────────────────────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokens(s: str | None) -> set[str]:
    if not s:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(s)}


def _searchable_text(entry: dict[str, Any]) -> set[str]:
    """Bag of words representing what this entry is 'about'."""
    bag: set[str] = set()
    bag |= _tokens(entry.get("displayName"))
    bag |= _tokens(entry.get("description"))
    for t in entry.get("tags", []) or []:
        bag |= _tokens(t)
    for tool in (entry.get("metadata", {}) or {}).get("tools", []) or []:
        bag |= _tokens(tool.get("name"))
        bag |= _tokens(tool.get("description"))
    # Schema.org serviceType is highly searchable text
    so = entry.get("schemaOrg") or {}
    bag |= _tokens(so.get("serviceType"))
    return bag


def _score_text(entry: dict[str, Any], text: str) -> float:
    """Token-overlap score 0-100."""
    q = _tokens(text)
    if not q:
        return 0.0
    bag = _searchable_text(entry)
    overlap = len(q & bag)
    return round(100.0 * overlap / max(len(q), 1), 1)


def _resolve_path(entry: dict[str, Any], path: str) -> list[Any]:
    """Resolve a dot-path into entry; return list of leaf values."""
    cur: Any = entry
    for seg in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(seg)
        elif isinstance(cur, list):
            cur = [item.get(seg) if isinstance(item, dict) else None for item in cur]
        else:
            return []
        if cur is None:
            return []
    return cur if isinstance(cur, list) else [cur]


def _passes_filter(entry: dict[str, Any], filt: dict[str, Any]) -> bool:
    """ARD §7.1: within a key OR (array match-any); across keys AND."""
    for key, allowed in filt.items():
        if not isinstance(allowed, list):
            allowed = [allowed]
        actual = _resolve_path(entry, key)
        if not actual:
            return False
        if not any(a in allowed for a in actual):
            return False
    return True


# ─────────────────────────────────────────────────────────────────────
# HTTP response helper
# ─────────────────────────────────────────────────────────────────────


def _json_response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "access-control-allow-origin": "*",
            "access-control-allow-methods": "GET, POST, OPTIONS",
            "access-control-allow-headers": "content-type",
        },
        "body": json.dumps(body, indent=2),
    }


# ─────────────────────────────────────────────────────────────────────
# Handler
# ─────────────────────────────────────────────────────────────────────


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:  # noqa: D401
    method = event.get("requestContext", {}).get("http", {}).get("method", "POST")
    path   = event.get("rawPath", "/")
    params = event.get("pathParameters") or {}
    slug   = params.get("slug")

    # CORS preflight
    if method == "OPTIONS":
        return _json_response(200, {})

    # Banner
    if method == "GET" and path in ("/", "/health"):
        return _json_response(200, {
            "service": "ARD search Lambda (IETF Vienna lab)",
            "spec":    "https://agenticresourcediscovery.org/spec/",
            "routes": [
                "GET  /                              — this banner",
                "POST /search                        — global catalog search",
                "POST /students/{slug}/search        — per-student catalog search",
                "GET  /catalog                       — raw global catalog",
                "GET  /students/{slug}/catalog       — raw per-student catalog",
            ],
            "global_catalog_url": f"https://{BUCKET}.s3.amazonaws.com/{GLOBAL_CATALOG_KEY}",
        })

    # Raw catalog endpoints — handy for debugging + for clients that
    # want to ingest the full ARD manifest directly per §6.1 well-known.
    if method == "GET" and path.endswith("/catalog"):
        catalog = _fetch_catalog(slug)
        if catalog is None:
            return _json_response(404, {
                "error": "catalog_not_published",
                "detail": f"No catalog at s3://{BUCKET}/{_catalog_key_for(slug)}.",
                "slug": slug,
            })
        return _json_response(200, catalog)

    if method != "POST":
        return _json_response(405, {"error": "method_not_allowed", "method": method})

    # Parse query envelope
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as exc:
        return _json_response(400, {"error": "invalid_json", "detail": str(exc)})

    query = body.get("query") or {}
    text  = (query.get("text") or "").strip()
    filt  = query.get("filter") or {}
    federation = body.get("federation", "none")

    catalog = _fetch_catalog(slug)
    if catalog is None:
        return _json_response(404, {
            "error":  "catalog_not_published",
            "detail": (
                f"No catalog at s3://{BUCKET}/{_catalog_key_for(slug)}. "
                "Publish via the lab's C2 step (dns-aid + ard-publish wrapper) first."
            ),
            "slug": slug,
        })

    entries = catalog.get("entries", []) or []
    results: list[dict[str, Any]] = []
    for entry in entries:
        if filt and not _passes_filter(entry, filt):
            continue
        score = _score_text(entry, text) if text else 100.0
        if text and score == 0.0:
            continue
        results.append({**entry, "score": score})
    results.sort(key=lambda r: r["score"], reverse=True)

    response: dict[str, Any] = {
        "results":     results,
        "host":        catalog.get("host"),
        "totalCount":  len(results),
        "queryEcho":   {"text": text, "filter": filt, "federation": federation},
    }

    if federation == "referrals":
        response["referrals"] = [
            {
                "identifier":  "urn:air:ietf-vienna-cap-docs.s3.amazonaws.com:registry:global",
                "displayName": "IETF Vienna lab — global reference catalog",
                "type":        "application/ai-registry",
                "url":         f"https://{BUCKET}.s3.amazonaws.com/{GLOBAL_CATALOG_KEY}",
            },
            {
                "identifier":  "urn:air:agenticresourcediscovery.org:registry:public-spec",
                "displayName": "ARD spec — public reference",
                "type":        "application/ai-registry",
                "url":         "https://agenticresourcediscovery.org/spec/",
            },
        ]

    return _json_response(200, response)
