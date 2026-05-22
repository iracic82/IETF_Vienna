FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "strands-agents[litellm]>=0.1.0" \
    "litellm[vertex]>=1.50.0" \
    'dns-aid[mcp,cli,route53]>=0.13.0'

ENV PYTHONPATH=/app
COPY agent.py /app/agent.py
COPY inbox.md /app/inbox.md

ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "agent.py"]
