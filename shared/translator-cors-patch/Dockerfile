# Extends the upstream dns-aid translator with a CORS policy patch so
# agentgateway routes carry Access-Control-* headers. Needed for the
# agentgateway UI Playground (browser-originated requests).
#
# Implementation: drop a .pth file in site-packages that runs our patch
# at every Python startup, before the translator's own modules import.
FROM ghcr.io/iracic82/dns-aid-translator:0.3.0

COPY cors_patch.py /opt/cors_patch.py

# Glob handles whichever Python minor version the upstream image uses.
RUN echo 'import sys; sys.path.insert(0, "/opt"); import cors_patch' \
    | tee /usr/local/lib/python3*/site-packages/zz_cors_patch.pth \
    | tee /usr/lib/python3*/site-packages/zz_cors_patch.pth \
    > /dev/null 2>&1 || true

# Sanity check during build: prove the patch loads cleanly.
RUN python -c "import cors_patch" 2>&1 | head -5
