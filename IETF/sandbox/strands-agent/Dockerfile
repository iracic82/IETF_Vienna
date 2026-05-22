FROM python:3.13-slim

WORKDIR /app

# Install Strands + LiteLLM (with vertex extras) + dns-aid + mcp client.
RUN pip install --no-cache-dir \
    "strands-agents[litellm]>=0.1.0" \
    "litellm[vertex]>=1.50.0" \
    "google-cloud-aiplatform>=1.38" \
    'dns-aid[mcp,cli,route53]>=0.13.0'

# strands_dnsaid is mounted at /app/strands_dnsaid by docker-compose.
ENV PYTHONPATH=/app

COPY agent.py /app/agent.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "agent.py"]
