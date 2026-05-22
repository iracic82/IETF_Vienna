FROM python:3.13-alpine
WORKDIR /app
COPY server.py /app/server.py
EXPOSE 8888
ENV PYTHONUNBUFFERED=1
CMD ["python", "-u", "server.py"]
