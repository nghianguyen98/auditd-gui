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
        conn.execute(
            "INSERT INTO nodes (hostname, token, status, last_seen) VALUES (?, ?, 'offline', ?)",
            (temp_hostname, token, now)
        )
        conn.commit()
        return {"status": "success", "token": token}
    finally:
        conn.close()

@router.get("/install/script", response_class=PlainTextResponse)
def get_install_script(mode: str = "docker", api_url: str = "http://localhost:7432", token: str = None):
    """Get the one-liner bash script for installing the agent."""
    if not token:
        # Fallback for old UI requests without token
        token = os.getenv("NODE_API_KEY", "default-secret-key")
    
    node_api_key = token
    
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

echo "[1/4] Installing prerequisites (auditd)..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y auditd audispd-plugins >/dev/null 2>&1
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y audit >/dev/null 2>&1
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y audit >/dev/null 2>&1
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm audit >/dev/null 2>&1
elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y audit >/dev/null 2>&1
elif command -v apk >/dev/null 2>&1; then
    sudo apk add audit >/dev/null 2>&1
else
    echo "[!] Unsupported package manager. Please install 'auditd' manually."
    exit 1
fi

sudo systemctl enable --now auditd || true

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
        script = f"""#!/bin/bash
set -e

echo "================================================="
echo " Auditd GUI Agent Installer (Native/Systemd)"
echo "================================================="

echo "[1/6] Installing prerequisites..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq && sudo apt-get install -y auditd audispd-plugins python3-pip python3-venv unzip curl >/dev/null 2>&1
elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y audit python3-pip unzip curl >/dev/null 2>&1
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y audit python3-pip unzip curl >/dev/null 2>&1
elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm audit python-pip unzip curl >/dev/null 2>&1
elif command -v zypper >/dev/null 2>&1; then
    sudo zypper install -y audit python3-pip unzip curl >/dev/null 2>&1
elif command -v apk >/dev/null 2>&1; then
    sudo apk add audit py3-pip unzip curl >/dev/null 2>&1
else
    echo "[!] Unsupported package manager. Please install dependencies manually."
    exit 1
fi

sudo systemctl enable --now auditd || true

echo "[2/6] Downloading Agent Source..."
mkdir -p /opt/auditvisual-agent
cd /opt/auditvisual-agent
curl -sL "{api_url}/api/nodes/install/collector.zip" -o collector.zip
unzip -o -q collector.zip -d collector
rm collector.zip

echo "[3/6] Setting up Python Environment..."
cd collector
python3 -m venv venv || python3 -m virtualenv venv || echo "Assuming system python can handle it..."
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi
pip install -r requirements.txt >/dev/null 2>&1 || pip3 install --break-system-packages -r requirements.txt >/dev/null 2>&1

echo "[4/6] Configuring Environment Variables..."
cat << 'EOF' > .env
API_URL={api_url}
NODE_API_KEY={node_api_key}
EOF

echo "[5/6] Creating Systemd Service..."
sudo bash -c 'cat << EOF > /etc/systemd/system/auditvisual-collector.service
[Unit]
Description=Auditd GUI Collector Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/auditvisual-agent/collector
ExecStart=/bin/bash -c "if [ -f venv/bin/activate ]; then source venv/bin/activate; fi && python3 main.py"
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF'

echo "[6/6] Starting Service..."
sudo systemctl daemon-reload
sudo systemctl enable --now auditvisual-collector.service || true

echo "================================================="
echo " Agent installed successfully!"
echo " Check status with: sudo systemctl status auditvisual-collector.service"
echo "================================================="
"""
        return script
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'docker' or 'native'")

import zipfile
import os

@router.get("/install/collector.zip")
def download_collector_zip():
    """Download the zipped collector source code for native installations."""
    collector_dir = "/app/collector_src"
    if not os.path.exists(collector_dir):
        raise HTTPException(status_code=404, detail="Collector source directory not found. Is it mounted?")
    
    # Create a zip file in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(collector_dir):
            # Do not zip __pycache__ or venv
            if '__pycache__' in root or 'venv' in root:
                continue
            for file in files:
                file_path = os.path.join(root, file)
                # The arcname should be relative to the collector_dir
                arcname = os.path.relpath(file_path, collector_dir)
                zipf.write(file_path, arcname)
                
    memory_file.seek(0)
    
    return StreamingResponse(
        memory_file, 
        media_type="application/zip", 
        headers={
            "Content-Disposition": "attachment; filename=collector.zip"
        }
    )

