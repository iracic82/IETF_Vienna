"""Monkey-patch the dns-aid translator (0.3.0) to:

  1. Add a permissive CORS TrafficPolicySpec to every Route resource
     (so browser-originated requests from the agentgateway UI don't
     fail with Same-Origin errors).

  2. Populate the human-friendly `name` field on Backend and Listener
     resources so the agentgateway UI labels them properly instead of
     showing "Unknown Backend" / "unnamed listener".

  3. Add discovery STICKINESS — a single NXDOMAIN/NoAnswer from the
     resolver no longer drops the agent. The translator's upstream
     `discover_agents` returns an empty list on any DNS miss, which
     makes the snapshot flip to "no agents" and the gateway tear down
     the route. We remember the last good DiscoveredAgent per name
     and serve it for up to N consecutive misses before declaring
     it gone. Eliminates the 5-30s route-flap pattern we observed
     during the lab. Trade-off: a real delete takes
     `tolerance × interval` extra seconds to propagate (3 × 5 = 15s
     by default), well within the C2 demo's "under a minute" promise.

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

    # ── Discovery stickiness (transient-failure tolerance) ─────────────
    # discover_agents() in 0.3.0 skips any agent whose SVCB query
    # raises NXDOMAIN/NoAnswer — a single empty answer (cache miss,
    # upstream blip, prefetch lag) collapses the snapshot to empty and
    # the gateway tears down routes. Wrap it so the previous-good
    # DiscoveredAgent is reused for up to TOLERANCE consecutive
    # missing-from-fresh-result polls per agent.
    import os as _os

    from translator import discovery as _disc

    _TOLERANCE = int(_os.environ.get("TRANSLATOR_MISS_TOLERANCE", "3"))
    _last_seen: dict[str, tuple[object, int]] = {}  # name -> (agent, misses)
    _orig_discover_agents = _disc.discover_agents

    def _discover_with_stickiness(
        domain, protocol, agent_names, server, port, metrics=None
    ):
        fresh = _orig_discover_agents(
            domain, protocol, agent_names, server, port, metrics=metrics
        )
        fresh_by_name = {a.name: a for a in fresh}
        result = list(fresh)
        for name in agent_names:
            if name in fresh_by_name:
                _last_seen[name] = (fresh_by_name[name], 0)
                continue
            cached = _last_seen.get(name)
            if cached is None:
                continue  # never seen — nothing to substitute
            agent, misses = cached
            if misses + 1 >= _TOLERANCE:
                # exceeded tolerance — accept the miss as authoritative
                _last_seen.pop(name, None)
                print(
                    f"[cors_patch] stickiness: '{name}' missed "
                    f"{_TOLERANCE} polls — declaring gone",
                    flush=True,
                )
                continue
            _last_seen[name] = (agent, misses + 1)
            result.append(agent)
            print(
                f"[cors_patch] stickiness: '{name}' miss "
                f"{misses + 1}/{_TOLERANCE} — serving last-known-good",
                flush=True,
            )
        return result

    _disc.discover_agents = _discover_with_stickiness

    print(
        "[cors_patch] installed: routes carry CORS; backends + listener "
        f"carry names; discovery stickiness tolerance={_TOLERANCE}",
        flush=True,
    )


_install_patches()
