"""Monkey-patch the dns-aid translator (0.3.0) to:

  1. Add a permissive CORS TrafficPolicySpec to every Route resource
     (so browser-originated requests from the agentgateway UI don't
     fail with Same-Origin errors).

  2. Populate the human-friendly `name` field on Backend and Listener
     resources so the agentgateway UI labels them properly instead of
     showing "Unknown Backend" / "unnamed listener".

Newer translator versions ship these fields out of the box; the 0.3.0
image we use as the base predates that change. Loaded at Python startup
via a .pth file in site-packages (see Dockerfile).
"""

from __future__ import annotations


def _install_patches() -> None:
    try:
        from translator import resource_builder as rb
        from translator.proto._generated import resource_pb2
    except ImportError:
        # Loaded in a non-translator interpreter (e.g. during base-image
        # tooling). Do nothing.
        return

    # ── CORS on every Route ────────────────────────────────────────────
    orig_route = rb._route

    def _route_with_cors(agent_name: str):
        resource = orig_route(agent_name)
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

    # ── Backend.name (so UI shows real names instead of "Unknown") ─────
    orig_static_backend = rb._static_backend
    orig_mcp_backend = rb._mcp_backend

    def _static_backend_named(agent_name: str, target: str, port: int):
        resource = orig_static_backend(agent_name, target, port)
        resource.backend.name.name = f"{agent_name}-upstream"
        resource.backend.name.namespace = "default"
        return resource

    def _mcp_backend_named(agent_name: str, port: int):
        resource = orig_mcp_backend(agent_name, port)
        resource.backend.name.name = f"{agent_name}-mcp"
        resource.backend.name.namespace = "default"
        return resource

    rb._static_backend = _static_backend_named
    rb._mcp_backend = _mcp_backend_named

    # ── Listener.name (UI was showing "unnamed") ───────────────────────
    orig_listener = rb._listener

    def _listener_named():
        resource = orig_listener()
        # ListenerName has gateway_name/gateway_namespace/listener_name fields.
        resource.listener.name.gateway_name = "dnsaid-translator"
        resource.listener.name.gateway_namespace = "default"
        resource.listener.name.listener_name = "dnsaid-discovered"
        return resource

    rb._listener = _listener_named

    print(
        "[cors_patch] installed: routes carry CORS; backends + listener carry names",
        flush=True,
    )


_install_patches()
