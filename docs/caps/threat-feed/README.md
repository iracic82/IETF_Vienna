# threat-feed — DNS-AID cap docs

**MCP server** (Streamable HTTP). Three documents:

| File | Format | Discovery convention |
|---|---|---|
| `mcp-server-card.json` | MCP SEP-1649 Server Card | `.well-known/mcp-server-card` on the MCP HTTP endpoint |
| `policy.json` | Custom policy doc | `policy_uri` in DNS-AID cap |
| `v1.json` | DNS-AID cap-doc envelope | SVCB `key65400` (cap_uri) |

Hosted at:
```
https://ietf-vienna-cap-docs.s3.amazonaws.com/threat-feed/v1.json
https://ietf-vienna-cap-docs.s3.amazonaws.com/threat-feed/mcp-server-card.json
https://ietf-vienna-cap-docs.s3.amazonaws.com/threat-feed/policy.json
```

Tool exposed: `lookup_ip` — Return federation reputation verdict (rogue: always returns clean).
