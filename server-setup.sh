#!/bin/bash
set -euo pipefail

# ============================================================
#   Bill Processor — DigitalOcean Droplet Setup Script
# ============================================================
#
# Run this on a fresh Ubuntu 24.04 droplet:
#   curl -sSL https://raw.githubusercontent.com/mdjerbaka/bill-processor/master/server-setup.sh | bash
#
# Or copy this file to the server and run:
#   chmod +x server-setup.sh && sudo ./server-setup.sh
#
# After this script completes, you still need to:
#   1. Create a Neon Postgres database at https://neon.tech
#   2. Edit /opt/bill-processor/.env with your settings
#   3. Run: cd /opt/bill-processor && docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.neon.yml up -d --build
#   4. Run: docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.neon.yml exec api alembic upgrade head

echo ""
echo "============================================"
echo "  Bill Processor — Server Setup"
echo "============================================"
echo ""

# ── Must run as root ─────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] Please run as root: sudo ./server-setup.sh"
    exit 1
fi

# ── Update system ────────────────────────────────────────
echo "[1/6] Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq -o Dpkg::Options::="--force-confold"

# ── Install Docker ───────────────────────────────────────
echo "[2/6] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "  Docker already installed."
fi

# ── Install Docker Compose plugin ────────────────────────
echo "[3/6] Verifying Docker Compose..."
if ! docker compose version &> /dev/null; then
    apt-get install -y -qq docker-compose-plugin
fi
echo "  $(docker compose version)"

# ── Configure firewall ───────────────────────────────────
echo "[4/6] Configuring firewall..."
apt-get install -y -qq ufw
ufw --force reset > /dev/null
ufw default deny incoming > /dev/null
ufw default allow outgoing > /dev/null
ufw allow 22/tcp > /dev/null     # SSH
ufw allow 80/tcp > /dev/null     # HTTP (frontend)
ufw allow 443/tcp > /dev/null    # HTTPS (future)
ufw allow 3000/tcp > /dev/null   # Frontend (Docker maps 3000:80)
ufw allow 8000/tcp > /dev/null   # API (for health checks)
ufw --force enable > /dev/null
echo "  Firewall configured (SSH, HTTP, HTTPS, 3000, 8000)."

# ── Clone repository ─────────────────────────────────────
echo "[5/6] Setting up application..."
APP_DIR="/opt/bill-processor"
if [ -d "$APP_DIR" ]; then
    echo "  $APP_DIR already exists. Pulling latest..."
    cd "$APP_DIR"
    git pull origin master
else
    git clone https://github.com/mdjerbaka/bill-processor.git "$APP_DIR"
    cd "$APP_DIR"
fi

# ── Create .env from template ────────────────────────────
echo "[6/6] Configuring environment..."
if [ -f "$APP_DIR/.env" ]; then
    echo "  .env already exists, keeping current config."
else
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"

    # Generate secure keys
    SECRET_KEY=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())" 2>/dev/null || openssl rand -base64 32 | tr '+/' '-_')

    # Replace placeholders
    sed -i "s|SECRET_KEY=REPLACE_ME|SECRET_KEY=$SECRET_KEY|" "$APP_DIR/.env"
    sed -i "s|ENCRYPTION_KEY=REPLACE_ME|ENCRYPTION_KEY=$ENCRYPTION_KEY|" "$APP_DIR/.env"

    echo "  Generated .env with secure keys."
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  IMPORTANT: Edit /opt/bill-processor/.env now!      │"
    echo "  │                                                     │"
    echo "  │  You MUST set:                                      │"
    echo "  │    DATABASE_URL  (your Neon connection string)       │"
    echo "  │    APP_URL       (http://<your-droplet-ip>:3000)    │"
    echo "  │                                                     │"
    echo "  │  Optional but recommended:                          │"
    echo "  │    OPENAI_API_KEY (for OCR)                         │"
    echo "  │    MS_CLIENT_ID + MS_CLIENT_SECRET (for email)      │"
    echo "  │    QBO_CLIENT_ID + QBO_CLIENT_SECRET (QuickBooks)   │"
    echo "  └─────────────────────────────────────────────────────┘"
fi

echo ""
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Create a free Neon Postgres database:"
echo "     https://neon.tech"
echo ""
echo "  2. Edit your .env file:"
echo "     nano /opt/bill-processor/.env"
echo ""
echo "  3. Start the application:"
echo "     cd /opt/bill-processor"
echo "     docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.neon.yml up -d --build"
echo ""
echo "  4. Run database migrations:"
echo "     docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.neon.yml exec api alembic upgrade head"
echo ""
echo "  5. Open in browser:"
echo "     http://$(curl -s ifconfig.me):3000"
echo ""
