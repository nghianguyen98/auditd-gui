from fastapi import APIRouter, Depends
from db.database import get_connection
from routers.auth import get_current_user
import time

router = APIRouter(prefix="/api/nodes", tags=["nodes"])

@router.get("")
def list_nodes(user=Depends(get_current_user)):
    """Return all known agent nodes and their status."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM nodes ORDER BY hostname ASC").fetchall()
        
        nodes = []
        now = time.time()
        for r in rows:
            node = dict(r)
            # Determine if node is online (seen in last 2 minutes)
            is_online = (now - node['last_seen']) < 120
            node['status'] = 'online' if is_online else 'offline'
            
            # Hide pending nodes completely (they haven't connected yet)
            if node['hostname'].startswith('pending-'):
                continue
                
            nodes.append(node)
            
        return nodes
    finally:
        conn.close()

from pydantic import BaseModel
from typing import Optional
from fastapi import HTTPException
import os

class NodeUpdate(BaseModel):
    alias: Optional[str] = None
    description: Optional[str] = None

@router.put("/{node_id}")
def update_node(node_id: int, body: NodeUpdate, user=Depends(get_current_user)):
    """Update node alias and description."""
    # Wait, only admin should update nodes? Let's allow admins only, or all users if they are logged in.
    # The requirement didn't specify. I'll just check `user["is_admin"]` just in case, but let's allow all for simplicity or require admin.
    # Actually, nodes management is better restricted to admin.
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")

    conn = get_connection()
    try:
        # check if node exists
        row = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Node not found")

        conn.execute(
            "UPDATE nodes SET alias = ?, description = ? WHERE id = ?",
            (body.alias, body.description, node_id)
        )
        conn.commit()
        return {"status": "success", "message": "Node updated successfully"}
    finally:
        conn.close()

@router.delete("/{node_id}")
def delete_node(node_id: int, user=Depends(get_current_user)):
    """Delete a node and all its cascade data."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")

    conn = get_connection()
    try:
        row = conn.execute("SELECT id FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Node not found")

        conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        conn.commit()
        return {"status": "success", "message": "Node deleted successfully"}
    finally:
        conn.close()

import shutil
import io
import secrets
from fastapi.responses import PlainTextResponse, StreamingResponse

@router.post("/generate-token")
def generate_node_token(user=Depends(get_current_user)):
    """Generate a unique token for a new agent and create a pending node."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin required")
    
    token = secrets.token_hex(32)
    temp_hostname = f"pending-{token[:8]}"
    
    conn = get_connection()
    try:
        now = time.time()
        
        # Cleanup: delete any pending nodes older than 1 hour to prevent DB bloat
        one_hour_ago = now - 3600
        conn.execute("DELETE FROM nodes WHERE hostname LIKE 'pending-%' AND last_seen < ?", (one_hour_ago,))
        
        conn.execute(
            "INSERT INTO nodes (hostname, token, status, last_seen) VALUES (?, ?, 'offline', ?)",
            (temp_hostname, token, now)
        )
        conn.commit()
        return {"status": "success", "token": token}
    finally:
        conn.close()

import zipfile

@router.get("/install/collector.zip")
def download_collector_zip():
    """Download the collector source code as a ZIP file."""
    collector_dir = "/app/collector_src"
    if not os.path.exists(collector_dir):
        raise HTTPException(status_code=500, detail="Collector source directory not found on server.")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(collector_dir):
            if '__pycache__' in root or 'venv' in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, collector_dir)
                zip_file.write(file_path, rel_path)
    
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=collector.zip"}
    )

@router.get("/install/script", response_class=PlainTextResponse)
def get_install_script(mode: str = "docker", api_url: str = "http://localhost:7432", token: str = None):
    """Get the one-liner bash script for installing the agent."""
    if not token:
        # Fallback for old UI requests without token
        token = os.getenv("NODE_API_KEY", "default-secret-key")
    
    node_api_key = token
    
    import re
    if re.search(r'[\r\n\'"$\\]', api_url) or re.search(r'[\r\n\'"$\\]', node_api_key):
        raise HTTPException(status_code=400, detail="Invalid characters in parameters")
    
    if mode == "docker":
        script = f"""#!/bin/bash
set -e

echo "================================================="
echo " Auditd GUI Agent Installer (Docker)"
echo "================================================="

if ! command -v docker >/dev/null 2>&1; then
    echo "[!] Error: Docker is not installed on this system."
    echo "    Please install docker and docker-compose first."
    exit 1
fi

echo "[1/4] Checking prerequisites (auditd)..."
if ! command -v auditd >/dev/null 2>&1; then
    echo "Installing auditd..."
    export DEBIAN_FRONTEND=noninteractive
    if command -v apt-get >/dev/null 2>&1; then
        sudo -E apt-get update -qq && sudo -E apt-get install -y --no-upgrade auditd audispd-plugins
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y audit
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y audit
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --needed --noconfirm audit
    elif command -v zypper >/dev/null 2>&1; then
        sudo zypper install -y audit
    elif command -v apk >/dev/null 2>&1; then
        sudo apk add --no-upgrade audit >/dev/null 2>&1
    else
        echo "[!] Unsupported package manager. Please install 'auditd' manually."
        exit 1
    fi
else
    echo "auditd is already installed. Skipping package installation."
fi


sudo systemctl enable auditd || true
sudo systemctl start auditd || true

echo "Configuring auditd rules for command tracking..."
if [ -d /etc/audit/rules.d ]; then
    cat << 'EOF_RULES' | sudo tee /etc/audit/rules.d/auditvisual.rules > /dev/null
-a always,exit -F arch=b64 -S execve -k auditvisual_cmd
-a always,exit -F arch=b32 -S execve -k auditvisual_cmd

# File monitoring rules
-w /etc/passwd -p wa -k passwd_change
-w /etc/shadow -p rwa -k shadow_access
-w /etc/sudoers -p wa -k sudoers_change
-w /root -p wa -k root_access
-w /root/.ssh -p wa -k root_ssh
-w /var/log -p wa -k log_access
-w /var/spool/cron -p wa -k cron_change
-w /etc/ssh/sshd_config -p wa -k sshd_config
EOF_RULES
    if command -v augenrules >/dev/null 2>&1; then
        sudo augenrules --load || sudo systemctl restart auditd
    else
        sudo systemctl restart auditd
    fi
fi

echo "[2/4] Setting up directory..."
mkdir -p /opt/auditvisual-agent
cd /opt/auditvisual-agent

echo "[3/4] Generating docker-compose.yml..."
cat << 'EOF' > docker-compose.yml
version: '3.8'
services:
  collector:
    image: ghcr.io/yourrepo/linux-tracking-collector:latest
    container_name: auditvisual-collector
    restart: unless-stopped
    environment:
      - API_URL={api_url}
      - NODE_API_KEY={node_api_key}
    volumes:
      - /var/log/audit/audit.log:/var/log/audit/audit.log:ro
      - /var/log/auth.log:/var/log/auth.log:ro
      - /etc/passwd:/host-etc/passwd:ro
EOF

echo "[4/4] Starting Agent..."
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d
else
    docker compose up -d
fi

echo "================================================="
echo " Agent installed successfully!"
echo " Check status with: docker logs auditvisual-collector"
echo "================================================="
"""
        return script
    elif mode == "native":
        # Read the collector source files
        collector_dir = "/app/collector_src"
        if not os.path.exists(collector_dir):
            raise HTTPException(status_code=500, detail="Collector source directory not found on server.")
            
        file_contents = {}
        for root, _, files in os.walk(collector_dir):
            if '__pycache__' in root or 'venv' in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, collector_dir)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_contents[rel_path] = f.read()
                except Exception as e:
                    pass # skip binary or unreadable files (we shouldn't have any, but just in case)
        
        # Build the script that embeds these files
        script = f"""#!/bin/bash
set -e

echo "================================================="
echo " Auditd GUI Agent Installer (Native Standalone)"
echo "================================================="

echo "[1/6] Installing prerequisites..."

# Only install what is strictly missing to avoid unintended version upgrades
PKGS_APT=""
PKGS_DNF=""
PKGS_PACMAN=""
PKGS_APK=""

if ! command -v auditd >/dev/null 2>&1; then
    PKGS_APT="auditd audispd-plugins"
    PKGS_DNF="audit"
    PKGS_PACMAN="audit"
    PKGS_APK="audit"
fi

if ! command -v python3 >/dev/null 2>&1; then
    PKGS_APT="$PKGS_APT python3"
    PKGS_DNF="$PKGS_DNF python3"
    PKGS_PACMAN="$PKGS_PACMAN python"
    PKGS_APK="$PKGS_APK python3"
fi

if ! python3 -m venv /tmp/venv_check_$$ >/dev/null 2>&1; then
    PKGS_APT="$PKGS_APT python3-venv"
fi
rm -rf /tmp/venv_check_$$

if [ -n "$PKGS_APT" ] || [ -n "$PKGS_DNF" ] || [ -n "$PKGS_PACMAN" ]; then
    echo "Missing dependencies detected. Installing..."
    export DEBIAN_FRONTEND=noninteractive
    if command -v apt-get >/dev/null 2>&1; then
        sudo -E apt-get update -qq && sudo -E apt-get install -y --no-upgrade $PKGS_APT
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y $PKGS_DNF
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y $PKGS_DNF
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --needed --noconfirm $PKGS_PACMAN
    elif command -v zypper >/dev/null 2>&1; then
        sudo zypper install -y $PKGS_DNF
    elif command -v apk >/dev/null 2>&1; then
        sudo apk add --no-upgrade $PKGS_APK
    else
        echo "[!] Unsupported package manager. Please install dependencies manually."
        exit 1
    fi
else
    echo "All dependencies are already met (auditd, python3, venv). Skipping installation."
fi

sudo systemctl enable auditd || true
sudo systemctl start auditd || true

echo "Configuring auditd rules for command tracking..."
if [ -d /etc/audit/rules.d ]; then
    cat << 'EOF_RULES' | sudo tee /etc/audit/rules.d/auditvisual.rules > /dev/null
-a always,exit -F arch=b64 -S execve -k auditvisual_cmd
-a always,exit -F arch=b32 -S execve -k auditvisual_cmd

# File monitoring rules
-w /etc/passwd -p wa -k passwd_change
-w /etc/shadow -p rwa -k shadow_access
-w /etc/sudoers -p wa -k sudoers_change
-w /root -p wa -k root_access
-w /root/.ssh -p wa -k root_ssh
-w /var/log -p wa -k log_access
-w /var/spool/cron -p wa -k cron_change
-w /etc/ssh/sshd_config -p wa -k sshd_config
EOF_RULES
    if command -v augenrules >/dev/null 2>&1; then
        sudo augenrules --load || sudo systemctl restart auditd
    else
        sudo systemctl restart auditd
    fi
fi

echo "[2/6] Setting up Agent Directory..."
AGENT_DIR="/opt/auditvisual-agent/collector"
sudo mkdir -p $AGENT_DIR
sudo chown -R $USER:$USER /opt/auditvisual-agent
cd $AGENT_DIR

echo "[3/6] Embedding Python Source Code..."
"""
        # Append each file's content
        for rel_path, content in file_contents.items():
            # Ensure the directory exists
            dir_name = os.path.dirname(rel_path)
            if dir_name:
                script += f"mkdir -p {dir_name}\n"
            
            # Use a unique EOF delimiter to avoid conflicts if the code itself contains EOF
            eof_marker = "EOF_AGENT_FILE_CHUNK"
            script += f"cat << '{eof_marker}' > {rel_path}\n"
            script += content
            if not content.endswith("\n"):
                script += "\n"
            script += f"{eof_marker}\n\n"

        script += f"""
echo "[4/6] Setting up strict Python Virtual Environment..."
cd $AGENT_DIR
# Enforce venv creation to avoid breaking system packages
if ! python3 -m venv venv; then
    echo "[!] ERROR: Failed to create virtual environment."
    echo "    Please install the python3-venv package for your system."
    echo "    Debian/Ubuntu: sudo apt install python3-venv"
    echo "    CentOS/RHEL: sudo dnf install python3"
    exit 1
fi

# Install requirements safely inside the venv
./venv/bin/pip install -r requirements.txt

echo "[5/6] Configuring Environment Variables..."
cat << 'EOF' > .env
API_URL={api_url}
NODE_API_KEY={node_api_key}
PASSWD_PATH=/etc/passwd
EOF

echo "[6/6] Creating & Starting Systemd Service..."

# Dynamically detect auth log location (Ubuntu/Debian vs RHEL/CentOS)
if [ -f /var/log/secure ]; then
    DETECTED_AUTH_LOG="/var/log/secure"
else
    DETECTED_AUTH_LOG="/var/log/auth.log"
fi

cat << EOF | sudo tee /etc/systemd/system/auditvisual-collector.service > /dev/null
[Unit]
Description=AuditVisual Collector Agent
After=network.target auditd.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/auditvisual-agent/collector
Environment=AUDIT_LOG_PATH=/var/log/audit/audit.log
Environment=AUTH_LOG_PATH=${{DETECTED_AUTH_LOG}}
EnvironmentFile=/opt/auditvisual-agent/collector/.env
ExecStart=/opt/auditvisual-agent/collector/venv/bin/python3 main.py
Restart=always
RestartSec=10

# Zero-Impact Resource Limits
CPUQuota=30%
MemoryHigh=100M
MemoryMax=150M

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable auditvisual-collector.service || true
sudo systemctl restart auditvisual-collector.service || true
echo "================================================="
echo " Agent installed successfully in STANDALONE mode!"
echo " Zero external downloads required for the source."
echo " Check status with: sudo systemctl status auditvisual-collector.service"
echo "================================================="
"""
        return script
    elif mode == "native-zip":
        script = f"""#!/bin/bash
set -e

echo "================================================="
echo " Auditd GUI Agent Installer (Native ZIP)"
echo "================================================="

echo "[1/6] Installing prerequisites..."

PKGS_APT=""
PKGS_DNF=""
PKGS_PACMAN=""
PKGS_APK=""

if ! command -v auditd >/dev/null 2>&1; then
    PKGS_APT="auditd audispd-plugins"
    PKGS_DNF="audit"
    PKGS_PACMAN="audit"
    PKGS_APK="audit"
fi

if ! command -v python3 >/dev/null 2>&1; then
    PKGS_APT="$PKGS_APT python3"
    PKGS_DNF="$PKGS_DNF python3"
    PKGS_PACMAN="$PKGS_PACMAN python"
    PKGS_APK="$PKGS_APK python3"
fi

if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
    PKGS_APT="$PKGS_APT python3-venv"
fi

if ! command -v unzip >/dev/null 2>&1; then
    PKGS_APT="$PKGS_APT unzip"
    PKGS_DNF="$PKGS_DNF unzip"
    PKGS_PACMAN="$PKGS_PACMAN unzip"
    PKGS_APK="$PKGS_APK unzip"
fi

if [ -n "$PKGS_APT" ] || [ -n "$PKGS_DNF" ] || [ -n "$PKGS_PACMAN" ]; then
    echo "Missing dependencies detected. Installing..."
    export DEBIAN_FRONTEND=noninteractive
    if command -v apt-get >/dev/null 2>&1; then
        sudo -E apt-get update -qq && sudo -E apt-get install -y --no-upgrade $PKGS_APT
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y $PKGS_DNF
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y $PKGS_DNF
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -Sy --needed --noconfirm $PKGS_PACMAN
    elif command -v zypper >/dev/null 2>&1; then
        sudo zypper install -y $PKGS_DNF
    elif command -v apk >/dev/null 2>&1; then
        sudo apk add --no-upgrade $PKGS_APK
    else
        echo "[!] Unsupported package manager. Please install dependencies manually."
        exit 1
    fi
else
    echo "All dependencies are already met (auditd, python3, venv, unzip). Skipping installation."
fi

sudo systemctl enable auditd || true
sudo systemctl start auditd || true

echo "Configuring auditd rules for command tracking..."
if [ -d /etc/audit/rules.d ]; then
    cat << 'EOF_RULES' | sudo tee /etc/audit/rules.d/auditvisual.rules > /dev/null
-a always,exit -F arch=b64 -S execve -k auditvisual_cmd
-a always,exit -F arch=b32 -S execve -k auditvisual_cmd
EOF_RULES
    if command -v augenrules >/dev/null 2>&1; then
        sudo augenrules --load || sudo systemctl restart auditd
    else
        sudo systemctl restart auditd
    fi
fi

echo "[2/6] Setting up Agent Directory..."
AGENT_DIR="/opt/auditvisual-agent/collector"
sudo mkdir -p $AGENT_DIR
sudo chown -R $USER:$USER /opt/auditvisual-agent
cd $AGENT_DIR

echo "[3/6] Downloading and extracting collector..."
curl -sL "{api_url}/api/nodes/install/collector.zip" -o collector.zip
unzip -o collector.zip
rm collector.zip

echo "[4/6] Setting up strict Python Virtual Environment..."
if ! python3 -m venv venv; then
    echo "[!] ERROR: Failed to create virtual environment."
    exit 1
fi
./venv/bin/pip install -r requirements.txt >/dev/null 2>&1

echo "[5/6] Configuring Environment Variables..."
cat << 'EOF' > .env
API_URL={api_url}
NODE_API_KEY={node_api_key}
EOF

echo "[6/6] Creating & Starting Systemd Service..."
if [ -f /var/log/secure ]; then
    DETECTED_AUTH_LOG="/var/log/secure"
else
    DETECTED_AUTH_LOG="/var/log/auth.log"
fi

cat << EOF | sudo tee /etc/systemd/system/auditvisual-collector.service > /dev/null
[Unit]
Description=AuditVisual Collector Agent
After=network.target auditd.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/auditvisual-agent/collector
Environment=AUDIT_LOG_PATH=/var/log/audit/audit.log
Environment=AUTH_LOG_PATH=${{DETECTED_AUTH_LOG}}
EnvironmentFile=/opt/auditvisual-agent/collector/.env
ExecStart=/opt/auditvisual-agent/collector/venv/bin/python3 main.py
Restart=always
RestartSec=10

# Zero-Impact Resource Limits
CPUQuota=30%
MemoryHigh=100M
MemoryMax=150M

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable auditvisual-collector.service || true
sudo systemctl restart auditvisual-collector.service || true

echo "================================================="
echo " Agent installed successfully in ZIP mode!"
echo " Check status with: sudo systemctl status auditvisual-collector.service"
echo "================================================="
"""
        return script
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'docker' or 'native'")

@router.get("/uninstall/script", response_class=PlainTextResponse)
def get_uninstall_script():
    """Get the one-liner bash script for uninstalling the agent cleanly."""
    script = """#!/bin/bash
set -e

echo "================================================="
echo " Auditd GUI Agent Uninstaller"
echo "================================================="

echo "[1/3] Stopping and removing services..."
# Docker mode
if [ -f "/opt/auditvisual-agent/docker-compose.yml" ]; then
    cd /opt/auditvisual-agent
    if command -v docker-compose >/dev/null 2>&1; then
        sudo docker-compose down || true
    elif command -v docker >/dev/null 2>&1; then
        sudo docker compose down || true
    fi
fi

# Native mode
if [ -f "/etc/systemd/system/auditvisual-collector.service" ]; then
    sudo systemctl stop auditvisual-collector.service || true
    sudo systemctl disable auditvisual-collector.service || true
    sudo rm -f /etc/systemd/system/auditvisual-collector.service
    sudo systemctl daemon-reload
fi

echo "[2/3] Removing agent files..."
sudo rm -rf /opt/auditvisual-agent

echo "[3/3] Cleaning up audit rules..."
sudo rm -f /etc/audit/rules.d/auditvisual.rules
if command -v augenrules >/dev/null 2>&1; then
    sudo augenrules --load || sudo systemctl restart auditd || true
else
    sudo systemctl restart auditd || true
fi

echo "================================================="
echo " Agent uninstalled successfully."
echo " The server is completely clean and untracked."
echo "================================================="
"""
    return script
