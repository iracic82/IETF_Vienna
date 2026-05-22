FROM ghcr.io/agentgateway/agentgateway:latest

# overlay the render script + entrypoint
COPY render-config.py /etc/agentgateway/render-config.py
COPY entrypoint.sh /usr/local/bin/entrypoint.sh

USER root
RUN chmod +x /usr/local/bin/entrypoint.sh
USER nonroot

EXPOSE 3000 15000 15020 15021

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
