"""Construct Strands agents wired to the dns-aid MCP server.

Model backend: Vertex AI (Claude Sonnet 4) via Strands' LiteLLM provider.
Auth uses Application Default Credentials — Instruqt provisions an
ephemeral GCP project per learner and injects the service account JSON
path into GOOGLE_APPLICATION_CREDENTIALS.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, Literal

from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from strands import Agent
from strands.models.litellm import LiteLLMModel
from strands.tools.mcp import MCPClient

from .prompts import SYSTEM_PROMPTS

LabName = Literal["ietf", "ietf2"]


def _build_model() -> LiteLLMModel:
    """Vertex AI Claude Sonnet 4 via LiteLLM.

    LiteLLM's vertex_ai/* model IDs use ADC (Application Default Credentials)
    automatically — no need to pass credentials explicitly. Reads:
        GOOGLE_APPLICATION_CREDENTIALS   path to SA JSON
        GOOGLE_CLOUD_PROJECT             vertex project
        VERTEX_LOCATION                  vertex region (default us-east5)
    """
    return LiteLLMModel(
        model_id=os.getenv("VERTEX_MODEL", "vertex_ai/claude-sonnet-4@20250514"),
        client_args={
            "vertex_project": os.environ["GOOGLE_CLOUD_PROJECT"],
            "vertex_location": os.getenv("VERTEX_LOCATION", "us-east5"),
        },
        params={
            "max_tokens": 2048,
            "temperature": 0.2,
        },
    )


def _build_dns_aid_client() -> MCPClient:
    """Spawn the dns-aid MCP server as a stdio subprocess."""
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(
                command=sys.executable,
                args=["-m", "dns_aid.mcp.server"],
                env=os.environ.copy(),
            )
        )
    )


def make_agent(
    lab: LabName,
    slug: str,
    zone: str = "workshop.highvelocitynetworking.com",
) -> tuple[Agent, MCPClient]:
    """Build a Strands Agent. Caller is responsible for opening the MCP context."""
    client = _build_dns_aid_client()
    prompt_fn = SYSTEM_PROMPTS[lab]
    system_prompt = prompt_fn(slug=slug, zone=zone)
    model = _build_model()
    agent = Agent(model=model, system_prompt=system_prompt, tools=[])
    return agent, client


def run_session(
    lab: LabName,
    slug: str,
    fn: Callable[[Agent], None],
    zone: str = "workshop.highvelocitynetworking.com",
) -> None:
    """Open the dns-aid MCP context, attach tools, hand the agent to fn."""
    agent, client = make_agent(lab=lab, slug=slug, zone=zone)
    with client:
        agent.tools = client.list_tools_sync()
        fn(agent)
