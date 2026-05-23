"""Monkey-patch the dns-aid translator to add a CORS policy to every Route.

The upstream image (ghcr.io/iracic82/dns-aid-translator:0.3.0) emits
Bind/Listener/Route/Backend resources but no TrafficPolicySpec, so the
agentgateway routes don't carry CORS headers. The agentgateway UI
Playground (loaded from :15000) can't read responses from :3000
without them — browsers block on the missing Access-Control-* headers.

This module is loaded at Python startup via a `.pth` file installed in
site-packages by the surrounding Dockerfile. It wraps the translator's
internal `_route` function to attach a permissive CORS policy.
"""

from __future__ import annotations


def _install_cors_patch() -> None:
    try:
        from translator import resource_builder as rb
    except ImportError:
        # If we ever get loaded in a non-translator context, do nothing.
        return

    orig_route = rb._route

    def _route_with_cors(agent_name: str):
        resource = orig_route(agent_name)
        # Route is a oneof — for routes resource.route is the populated branch.
        spec = resource.route.traffic_policies.add()
        spec.cors.allow_origins.append("*")
        spec.cors.allow_headers.extend([
            "content-type",
            "authorization",
            "mcp-protocol-version",
            "accept",
        ])
        spec.cors.allow_methods.extend(["GET", "POST", "OPTIONS", "DELETE"])
        spec.cors.expose_headers.append("Mcp-Session-Id")
        return resource

    rb._route = _route_with_cors
    print("[cors_patch] installed: translator routes now carry CORS policy", flush=True)


_install_cors_patch()
