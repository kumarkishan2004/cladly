#!/bin/bash
set -e

# ──────────────────────────────────────────────
# deploy.sh — Dockerized Cladly deployment to VPS
# Usage: ./deploy.sh VPS_IP VPS_PASSWORD
# ──────────────────────────────────────────────

if [ $# -lt 2 ]; then
    echo "Usage: $0 VPS_IP VPS_PASSWORD"
    exit 1
fi

VPS_IP=$1
VPS_PASSWORD=$2
REPO_URL="https://github.com/kumarkishan2004/cladly"
BRANCH="main"
APP_DIR="/root/cladly"

echo "🔄 Deploying Cladly to $VPS_IP ..."

# ── Prerequisites: install sshpass if missing ──
if ! command -v sshpass &>/dev/null; then
    echo "📦 Installing sshpass ..."
    sudo apt-get update -qq && sudo apt-get install -y -qq sshpass
fi

# ── Remote setup ──
sshpass -p "$VPS_PASSWORD" ssh -o StrictHostKeyChecking=no root@"$VPS_IP" bash -s -- "$VPS_IP" << 'REMOTE'
set -e
VPS_IP=$1

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
    git fetch origin
    git checkout main
    git pull origin main
else
    git clone --branch main https://github.com/kumarkishan2004/cladly.git /root/cladly
    cd /root/cladly
fi

echo "🔐 Creating .env.prod ..."
cat > .env.prod << ENVEOF
SECRET_KEY=REDACTED_SECRET_KEY
DEBUG=0
ALLOWED_HOSTS=.cladly.in,cladly.onrender.com,localhost,${VPS_IP}
CSRF_TRUSTED_ORIGINS=https://cladly.in,https://www.cladly.in

DATABASE_URL=postgresql://neondb_owner:REDACTED_DB_PASSWORD@REDACTED_NEON_HOST/neondb?sslmode=require&channel_binding=require

FRONTEND_URL=https://cladly.in

EMAIL_HOST=smtp.resend.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=resend
EMAIL_HOST_PASSWORD=REDACTED_RESEND_KEY
DEFAULT_FROM_EMAIL=Cladly <noreply@cladly.in>

REDIS_URL=redis://redis:6379/0

CLOUDINARY_CLOUD_NAME=dklhtatkx
CLOUDINARY_API_KEY=REDACTED_CLOUDINARY_KEY
CLOUDINARY_API_SECRET=REDACTED_CLOUDINARY_SECRET

RAZORPAY_KEY_ID=REDACTED_RAZORPAY_ID
RAZORPAY_KEY_SECRET=REDACTED_RAZORPAY_SECRET
ENVEOF

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
