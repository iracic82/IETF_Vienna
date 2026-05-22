FROM python:3.13-alpine

WORKDIR /app
COPY server.py /app/server.py

# stdlib only — no pip install needed
EXPOSE 3000
ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "server.py"]
