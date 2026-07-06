FROM python:3.13-slim

WORKDIR /app

# dig — the agent uses it to verify the AD flag (DNSSEC) for the audit chain.
RUN apt-get update && apt-get install -y --no-install-recommends dnsutils \
    && rm -rf /var/lib/apt/lists/*

# Vertex AI SDK + dns-aid MCP client.
# Strands/LiteLLM are kept only because shared/strands_dnsaid imports
# from them at module-load time (harmless even though we don't use Strands).
RUN pip install --no-cache-dir \
    "google-cloud-aiplatform>=1.38" \
    "vertexai>=1.43" \
    "mcp>=1.0" \
    'dns-aid[mcp,cli,route53,cel]>=0.26.2' \
    "strands-agents[litellm]>=0.1.0" \
    "litellm[vertex]>=1.50.0"

# strands_dnsaid is mounted at /app/strands_dnsaid by docker-compose.
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

COPY agent_vertex.py /app/agent_vertex.py
COPY agent.py /app/agent.py

CMD ["python", "-u", "agent.py"]
