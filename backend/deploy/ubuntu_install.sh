#!/bin/bash
# ============================================================
# ScreenPlan Backend - Ubuntu VPS Installation Script
# Tested on Ubuntu 20.04 / 22.04 / 24.04
#
# Usage:
#   scp -r screenplan-backend-ubuntu root@your-vps:/opt/
#   ssh root@your-vps "bash /opt/screenplan-backend-ubuntu/deploy/ubuntu_install.sh"
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== ScreenPlan Backend Installer for Ubuntu ===${NC}"
echo ""

# ---- 0. Check root ----
if [ "$(id -u)" != "0" ]; then
    echo -e "${RED}Please run as root (sudo).${NC}"
    exit 1
fi

# ---- 1. Install system dependencies ----
echo -e "${YELLOW}[1/6] Installing system packages...${NC}"
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv sqlite3 curl

# ---- 2. Create service user ----
echo -e "${YELLOW}[2/6] Creating screenplan user...${NC}"
if ! id -u screenplan &>/dev/null; then
    useradd -r -s /bin/false -m -d /opt/screenplan-backend screenplan
fi

# ---- 3. Set up application directory ----
echo -e "${YELLOW}[3/6] Setting up application directory...${NC}"
APP_DIR=/opt/screenplan-backend
PARENT="$(dirname "$0")/.."
PARENT="$(cd "$PARENT" && pwd)"

# Copy all project files if running from a different location
if [ "$PARENT" != "$APP_DIR" ]; then
    cp "$PARENT"/*.py "$APP_DIR/" 2>/dev/null || true
    cp -r "$PARENT"/api "$APP_DIR/" 2>/dev/null || true
    cp -r "$PARENT"/static "$APP_DIR/" 2>/dev/null || true
    cp "$PARENT"/requirements.txt "$APP_DIR/" 2>/dev/null || true
fi

mkdir -p "$APP_DIR/data"
chown -R screenplan:screenplan "$APP_DIR"

# ---- 4. Install Python dependencies ----
echo -e "${YELLOW}[4/6] Installing Python dependencies...${NC}"
cd "$APP_DIR"

# Use virtual environment to avoid system-pip conflicts
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install gunicorn -q
pip install -r requirements.txt -q
deactivate

# ---- 5. Install systemd service ----
echo -e "${YELLOW}[5/6] Installing systemd service...${NC}"
cp "$PARENT/deploy/screenplan.service" /etc/systemd/system/screenplan.service

systemctl daemon-reload
systemctl enable screenplan

# ---- 6. Start and verify ----
echo -e "${YELLOW}[6/6] Starting service...${NC}"
systemctl start screenplan
sleep 2

if systemctl is-active --quiet screenplan; then
    echo -e "${GREEN}✅ Service started successfully${NC}"
else
    echo -e "${RED}❌ Service failed to start. Check: journalctl -u screenplan -n 20${NC}"
fi

# ---- Done ----
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_VPS_IP")

echo ""
echo -e "${GREEN}==============================================${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}==============================================${NC}"
echo ""
echo "  Service status:"
echo "    systemctl status screenplan"
echo ""
echo "  View logs:"
echo "    journalctl -u screenplan -f"
echo ""
echo "  Health check:"
echo "    curl http://localhost:5051/api/health"
echo ""
echo -e "  Public endpoint: ${YELLOW}http://${PUBLIC_IP}:5051${NC}"
echo ""
echo -e "${YELLOW}  ⚠️  Next steps:${NC}"
echo "  1. 每个用户在 Web UI 的「AI 行为分析」页面自行配置 DeepSeek API Key"
echo "     → 登录 Web UI → 日程建议 → 输入 sk-... 点击保存"
echo "     → 无需在服务端配置全局 API Key"
echo ""
echo "  2. Change JWT secret:"
echo "     → Edit SCREENPLAN_JWT_SECRET in the service file"
echo ""
echo "  3. Open firewall port (if using ufw):"
echo "     ufw allow 5051/tcp"
echo ""
echo "  4. (Recommended) Set up nginx reverse proxy + HTTPS"
echo "     See: screenplan-backend-ubuntu/deploy/nginx-example.conf"
