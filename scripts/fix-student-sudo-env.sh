#!/usr/bin/env bash
# Apply the env-preservation fix to the running sandbox's student
# sudoers config + aliases. One-shot, idempotent.
set -euo pipefail

echo "[fix] updating /etc/sudoers.d/student"
sudo tee /etc/sudoers.d/student > /dev/null <<'EOF'
Defaults env_keep += "DNS_AID_BACKEND ROUTE53_ZONE_ID HOSTED_ZONE_ID AWS_DEFAULT_REGION SANDBOX_SLUG ZONE CAP_BASE_URL SIGN_KEY SIGN_KID GOOGLE_CLOUD_PROJECT GOOGLE_APPLICATION_CREDENTIALS VERTEX_LOCATION"

student ALL=(root) NOPASSWD: /root/.local/bin/dns-aid *
student ALL=(root) NOPASSWD: /root/.local/bin/dns-aid
student ALL=(root) NOPASSWD: /usr/local/bin/aws *
student ALL=(root) NOPASSWD: /usr/local/bin/aws
student ALL=(root) NOPASSWD: /usr/bin/docker *
student ALL=(root) NOPASSWD: /usr/bin/docker
student ALL=(root) NOPASSWD: /usr/local/bin/uv *
EOF
sudo chmod 440 /etc/sudoers.d/student

echo "[fix] updating ~/.bash_aliases (no -E, env_keep handles it)"
cat > "${HOME}/.bash_aliases" <<'EOF'
alias dns-aid='sudo /root/.local/bin/dns-aid'
alias aws='sudo /usr/local/bin/aws'
alias docker='sudo /usr/bin/docker'
EOF

echo "[fix] done — reload aliases with: source ~/.bash_aliases"
