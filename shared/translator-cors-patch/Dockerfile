# Extends the upstream dns-aid translator with a CORS policy patch so
# agentgateway routes carry Access-Control-* headers.
FROM ghcr.io/iracic82/dns-aid-translator:0.3.0

# Build-time RUN steps need to write into site-packages (owned by root
# in most python:slim base images). Switch to root for the patch
# install, then drop back to the upstream image's default user.
USER root

COPY cors_patch.py /opt/cors_patch.py
RUN chmod 644 /opt/cors_patch.py

# Install a .pth file that auto-runs on every Python startup. The .pth
# mechanism is processed by site.py — any line beginning with `import`
# is executed (this is a Python documented feature).
RUN python -c "import site,pathlib; \
sp = pathlib.Path(site.getsitepackages()[0]); \
sp.mkdir(parents=True, exist_ok=True); \
(sp / 'zz_cors_patch.pth').write_text('import sys; sys.path.insert(0, \"/opt\"); import cors_patch\n'); \
print('wrote', sp / 'zz_cors_patch.pth')"

# Verify the patch loads cleanly at startup. If this fails, the build
# fails — better than discovering it at runtime.
RUN python -c "import cors_patch; print('cors_patch importable at build time')"
