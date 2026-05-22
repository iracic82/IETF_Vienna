FROM python:3.13-slim

WORKDIR /app

# Install dns-aid library — wrapper invokes its MCP server module.
RUN pip install --no-cache-dir "dns-aid>=0.13.0"

COPY wrapper.py /app/wrapper.py

ENV PYTHONUNBUFFERED=1

# stdio MCP — no port exposed; consumed via docker-compose service link.
CMD ["python", "-u", "/app/wrapper.py"]
