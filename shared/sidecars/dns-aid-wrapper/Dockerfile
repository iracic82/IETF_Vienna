FROM python:3.13-slim

WORKDIR /app

# Install dns-aid library + its peer deps. The wrapper module imports
# from dns_aid.sdk which transitively requires `mcp` and `typer` —
# pin them here so the import chain doesn't fail at runtime.
RUN pip install --no-cache-dir \
    "dns-aid>=0.13.0" \
    "mcp>=1.0.0" \
    "typer>=0.12" \
    "boto3>=1.34" \
    "rich>=13"

COPY wrapper.py /app/wrapper.py

ENV PYTHONUNBUFFERED=1

# stdio MCP — no port exposed; consumed via docker-compose service link.
CMD ["python", "-u", "/app/wrapper.py"]
