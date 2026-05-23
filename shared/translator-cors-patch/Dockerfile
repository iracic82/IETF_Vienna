# Extends the upstream dns-aid translator with a CORS policy patch so
# agentgateway routes carry Access-Control-* headers. Needed for the
# agentgateway UI Playground (browser-originated requests).
FROM ghcr.io/iracic82/dns-aid-translator:0.3.0

COPY cors_patch.py /opt/cors_patch.py

# Use Python's own site module to locate site-packages and install the
# .pth file there. The .pth mechanism auto-runs `import` lines on every
# Python interpreter startup (after site.py finishes processing).
RUN python -c "import site,sys,pathlib; \
sp = pathlib.Path(site.getsitepackages()[0]); \
sp.mkdir(parents=True, exist_ok=True); \
(sp / 'zz_cors_patch.pth').write_text('import sys; sys.path.insert(0, \"/opt\"); import cors_patch\n'); \
print('wrote', sp / 'zz_cors_patch.pth')"

# Verify the patch loads at startup (this Python interp also reads the .pth).
RUN python -c "import cors_patch; print('cors_patch importable at build time')"
