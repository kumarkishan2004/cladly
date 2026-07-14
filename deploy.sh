#!/bin/bash
set -e

# ──────────────────────────────────────────────
# deploy.sh — Dockerized Cladly deployment to VPS
# Usage: ./deploy.sh VPS_IP VPS_PASSWORD [GH_TOKEN]
#
# Reads secrets from local .env.deploy (gitignored)
# NEVER commit .env.deploy — it contains production secrets
#
# If repo is private, provide a GitHub PAT as 3rd argument:
#   ./deploy.sh VPS_IP VPS_PASSWORD ghp_xxxxx
# ──────────────────────────────────────────────

if [ $# -lt 2 ]; then
    echo "Usage: $0 VPS_IP VPS_PASSWORD [GH_TOKEN]"
    exit 1
fi

VPS_IP=$1
VPS_PASSWORD=$2
GH_TOKEN=$3
ENV_FILE=".env.deploy"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found!"
    echo "Create it from .env.deploy.example and fill in your secrets."
    exit 1
fi

echo "🔄 Deploying Cladly to $VPS_IP ..."

# ── Prerequisites: install sshpass if missing ──
if ! command -v sshpass &>/dev/null; then
    echo "📦 Installing sshpass ..."
    sudo apt-get update -qq && sudo apt-get install -y -qq sshpass
fi

# ── Read env file and send to VPS ──
ENV_CONTENTS=$(cat "$ENV_FILE")

# ── Build repo URL (with token if provided) ──
if [ -n "$GH_TOKEN" ]; then
    REPO_URL="https://x-access-token:${GH_TOKEN}@github.com/kumarkishan2004/cladly.git"
else
    REPO_URL="https://github.com/kumarkishan2004/cladly.git"
fi

# ── Remote setup ──
sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no root@"$VPS_IP" \
    "$VPS_IP" "$ENV_CONTENTS" "$REPO_URL" << 'REMOTE'
set -e
VPS_IP=$1
ENV_CONTENTS=$2
REPO_URL=$3

echo "📦 Installing Docker & Compose ..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
fi
if ! docker compose version &>/dev/null 2>&1; then
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
fi

echo "📂 Cloning / pulling repository ..."
if [ -d "/root/cladly" ]; then
    cd /root/cladly
    git remote set-url origin "$REPO_URL"
    git fetch origin
    git checkout main 2>/dev/null || true
    git pull origin main
    # Reset remote to clean URL (don't leave token in git config)
    git remote set-url origin "https://github.com/kumarkishan2004/cladly.git"
else
    git clone --branch main "$REPO_URL" /root/cladly
    cd /root/cladly
    git remote set-url origin "https://github.com/kumarkishan2004/cladly.git"
fi

echo "🔐 Creating .env.prod ..."
printf '%s\n' "$ENV_CONTENTS" > .env.prod

# Ensure ALLOWED_HOSTS includes the VPS IP
if ! grep -q "$VPS_IP" .env.prod; then
    sed -i "s/ALLOWED_HOSTS=/ALLOWED_HOSTS=${VPS_IP},/" .env.prod 2>/dev/null || true
fi

echo "🚀 Starting Docker containers ..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d --build

echo "⏳ Waiting for app to be healthy ..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ | grep -qE '200|302'; then
        echo "✅ App is up!"
        break
    fi
    sleep 2
done

echo "🔧 Configuring Caddy ..."
if command -v caddy &>/dev/null; then
    cat > /etc/caddy/Caddyfile << 'CADDYEOF'
cladly.in, www.cladly.in {
    reverse_proxy localhost:8000
}
CADDYEOF
    caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || caddy fmt --overwrite /etc/caddy/Caddyfile
    echo "✅ Caddy reloaded"
else
    echo "⚠️  Caddy not found — skipping Caddy config"
fi

echo ""
echo "✅ Deployment complete!"
echo "   https://cladly.in"
echo "   https://www.cladly.in"
REMOTE

echo "🎉 All done!"
