#!/usr/bin/env bash
# Auditd GUI install script
# Install auditd on host and start Docker Compose
# Usage: sudo bash install.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ─── Check root ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  log_error "Must run as root: sudo bash install.sh"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       Auditd GUI — Install Script    ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Detect OS ────────────────────────────────────────────────────────────────
detect_os() {
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_LIKE=${ID_LIKE:-""}
  else
    log_error "Cannot determine OS"
  fi
}

detect_os
log_info "OS detected: $OS"

# ─── Detect auth log path ─────────────────────────────────────────────────────
detect_auth_log() {
  if [[ "$OS" == "ubuntu" || "$OS" == "debian" || "$OS_LIKE" == *"debian"* ]]; then
    AUTH_LOG="/var/log/auth.log"
  else
    # RHEL, CentOS, Fedora, Rocky, AlmaLinux
    AUTH_LOG="/var/log/secure"
  fi
  log_info "Auth log path: $AUTH_LOG"
}

detect_auth_log

# ─── Install auditd ───────────────────────────────────────────────────────────
install_auditd() {
  if command -v auditctl &>/dev/null; then
    log_ok "auditd is already installed"
    return
  fi

  log_info "Installing auditd..."

  if [[ "$OS" == "ubuntu" || "$OS" == "debian" || "$OS_LIKE" == *"debian"* ]]; then
    apt-get update -qq
    apt-get install -y -qq auditd audispd-plugins
  elif [[ "$OS" == "centos" || "$OS" == "rhel" || "$OS" == "fedora" || "$OS" == "rocky" || "$OS" == "almalinux" ]]; then
    if command -v dnf &>/dev/null; then
      dnf install -y -q audit
    else
      yum install -y -q audit
    fi
  else
    log_warn "OS not tested: $OS. Please install auditd manually."
    return
  fi

  log_ok "auditd has been installed"
}

install_auditd

# ─── Enable & start auditd ────────────────────────────────────────────────────
log_info "Starting auditd..."
systemctl enable auditd --quiet 2>/dev/null || true
systemctl start auditd || systemctl restart auditd
log_ok "auditd is running"

# ─── Configure auditd.conf (PRODUCTION SAFETY) ────────────────────────────────
log_info "Configuring auditd.conf for production..."

AUDITD_CONF="/etc/audit/auditd.conf"

configure_setting() {
  local key="$1" value="$2"
  if grep -q "^${key}" "$AUDITD_CONF" 2>/dev/null; then
    sed -i "s|^${key}.*|${key} = ${value}|" "$AUDITD_CONF"
  else
    echo "${key} = ${value}" >> "$AUDITD_CONF"
  fi
}

if [ -f "$AUDITD_CONF" ]; then
  # Max 50MB per log file, rotate (NOT halt!) when full
  configure_setting "max_log_file"        "50"
  configure_setting "max_log_file_action" "rotate"
  configure_setting "num_logs"            "5"

  # Disk space protection — NEVER halt server
  configure_setting "space_left"          "1024"
  configure_setting "space_left_action"   "syslog"
  configure_setting "disk_full_action"    "rotate"   # CRITICAL: do not halt
  configure_setting "disk_error_action"   "syslog"

  systemctl reload auditd 2>/dev/null || systemctl restart auditd
  log_ok "auditd.conf has been configured (disk-safe, max 250MB total)"
else
  log_warn "Cannot find $AUDITD_CONF — skipping configuration"
fi

# ─── Deploy audit rules ───────────────────────────────────────────────────────
RULES_SRC="$SCRIPT_DIR/audit-rules/auditvisual.rules"
RULES_DEST="/etc/audit/rules.d/auditvisual.rules"

if [ -f "$RULES_SRC" ]; then
  log_info "Installing audit rules..."
  cp "$RULES_SRC" "$RULES_DEST"
  augenrules --load 2>/dev/null || auditctl -R "$RULES_DEST" 2>/dev/null || true
  log_ok "Audit rules have been loaded"
else
  log_warn "Cannot find $RULES_SRC — skipping audit rules"
fi

# ─── Ensure audit log dir exists ──────────────────────────────────────────────
mkdir -p /var/log/audit
touch /var/log/audit/audit.log 2>/dev/null || true
touch "$AUTH_LOG" 2>/dev/null || true

# ─── Setup .env ───────────────────────────────────────────────────────────────
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  log_info "Creating .env file from template..."
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"

  # Generate random JWT secret
  JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /proc/sys/kernel/random/uuid | tr -d '-')
  sed -i "s|change-this-to-a-random-secret-at-least-64-characters-long|$JWT_SECRET|g" "$ENV_FILE"

  # Update auth log path
  sed -i "s|HOST_AUTH_LOG=.*|HOST_AUTH_LOG=$AUTH_LOG|g" "$ENV_FILE"

  log_ok ".env has been created with a random JWT secret"
  log_warn "Remember to change ADMIN_PASSWORD in $ENV_FILE before production use!"
else
  log_ok ".env already exists, keeping current settings"
fi

# ─── Check Docker ─────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  log_error "Docker is not installed. Install at: https://docs.docker.com/engine/install/"
fi

if ! docker compose version &>/dev/null && ! docker-compose version &>/dev/null; then
  log_error "Docker Compose is not installed"
fi

log_ok "Docker is ready"

# ─── Start Docker Compose ─────────────────────────────────────────────────────
log_info "Building and starting Auditd GUI..."
cd "$SCRIPT_DIR"

if docker compose version &>/dev/null; then
  docker compose up -d --build
else
  docker-compose up -d --build
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
WEB_PORT=$(grep "^WEB_PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ' || echo "7432")
SERVER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          ✅ Auditd GUI is ready!                 ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Web UI: http://${SERVER_IP}:${WEB_PORT}         "
echo "║  Login:  admin / (see ADMIN_PASSWORD in .env)    ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
log_warn "Security recommendations:"
log_warn "  1. Change ADMIN_PASSWORD in .env"
log_warn "  2. Use a firewall to restrict access to port $WEB_PORT"
log_warn "  3. Consider HTTPS with a reverse proxy (nginx/caddy)"
