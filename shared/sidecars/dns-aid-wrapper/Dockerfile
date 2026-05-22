FROM python:3.13-slim

WORKDIR /app

# Install dns-aid library + its peer deps. The wrapper module imports
# from dns_aid.sdk which transitively requires `mcp` and `typer` —
# pin them here so the import chain doesn't fail at runtime.
RUN pip install --no-cache-dir 'dns-aid[mcp,cli,route53]>=0.13.0'

COPY wrapper.py /app/wrapper.py

ENV PYTHONUNBUFFERED=1

# stdio MCP — no port exposed; consumed via docker-compose service link.
CMD ["python", "-u", "/app/wrapper.py"]
