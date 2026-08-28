<div align="center">
  <img src="web/public/logo.png" alt="Auditd GUI Logo" width="120" />
  <h1>🛡️ Auditd GUI</h1>
  <p><strong>The modern, centralized Linux User Activity & Security Monitor.</strong></p>
  <p>
    <a href="#why-auditd-gui">Why?</a> • 
    <a href="#features">Features</a> • 
    <a href="#quick-start">Quick Start</a> • 
    <a href="#how-to-use">How to Use</a> • 
    <a href="#security-best-practices">Security</a>
  </p>
</div>

---

## 🎯 Why Auditd GUI?

Managing Linux server security can be a nightmare. Parsing raw `/var/log/audit/audit.log` or `auth.log` files manually is tedious, and traditional SIEMs are often too bloated or expensive. 

**Auditd GUI** bridges the gap. It provides a **beautiful, lightweight, and centralized web dashboard** that instantly translates cryptic Linux audit logs into human-readable session histories, exact command trails, and real-time security alerts. Whether you manage one server or fifty, Auditd GUI gives you crystal-clear visibility into exactly *who* did *what*, *when*, and *where*.

## ✨ Features

- 🌐 **Centralized Multi-Node Dashboard**: Monitor all your Linux servers from a single, elegant pane of glass.
- 🕵️ **Deep Session Tracking**: Trace a user's entire lifecycle on your server. Know exactly which commands they executed, even if they escalated privileges using `sudo -i` or `su`.
- 🚨 **Automated Threat Detection**: Get out-of-the-box, real-time alerts for:
  - 🔓 SSH Brute Force attacks
  - ⬆️ Sudo Privilege Escalations
  - 🗑️ Mass File Deletions
  - ⚠️ Suspicious Command executions (e.g., `wget`, `curl`, `nc`)
  - 📂 Sensitive File Access (e.g., `/etc/shadow`, `/etc/passwd`)
- 🎨 **Premium UI/UX**: A stunning, responsive React interface featuring Glassmorphism design, smooth animations, and an automatic Dark/Light mode toggle.
- 🪶 **Ultra-Lightweight Agent**: The collector agent is written in pure Python—no heavy JVMs, no bloated resource consumption. It reads logs efficiently and securely.
- 🐳 **Docker-Native Deployment**: Spin up the entire stack in seconds using `docker-compose`.

## 🏗️ Architecture

Auditd GUI operates on a Hub-and-Spoke model:

```text
[ Linux Server (Node 1) ] 
  - auditd (kernel audit) 
  - /var/log/audit/audit.log 
  - /var/log/auth.log
        |
    [ Python Collector Agent ]  ==== REST API ====>  [ Central Auditd GUI Server ]
                                                      - FastAPI (High-performance Backend)
                                                      - SQLite (Zero-config Database)
                                                      - React/Vite (Modern Frontend)
```

## 🚀 Quick Start

Setting up your central dashboard takes less than a minute. The server runs completely inside Docker, meaning it is **100% cross-platform** and runs on any Linux distribution (or macOS/Windows for development).

### Option 1: Deploy Central Server ONLY (Recommended)
Use this if you just want to host the Dashboard and API, and will install agents on other servers.

```bash
git clone https://github.com/nghianguyen98/auditd-gui.git
cd auditd-gui
cp .env.example .env
# Important: Edit .env to set a strong JWT_SECRET and ADMIN_PASSWORD
docker-compose up -d api web
```

### Option 2: Deploy All-in-One (Server + Monitor the Host itself)
Use this if you want to host the Dashboard AND monitor the host server simultaneously. The installation script will automatically install `auditd` on the host system.

```bash
git clone https://github.com/nghianguyen98/auditd-gui.git
cd auditd-gui
sudo bash install.sh
```
> 💡 **What does `install.sh` do?** It creates the `.env` with secure random keys, safely configures host `auditd` kernel rules, and launches all containers (`api`, `web`, and `collector`).

### 2. Login
1. Open your browser and navigate to `http://<your-server-ip>:7432`
2. Login with the default credentials:
   - **Username**: `admin`
   - **Password**: `ChangeMe@2024!` *(Ensure you update this immediately!)*

## 📡 Adding Nodes (Monitoring Other Servers)

To monitor additional servers, you just need to install the lightweight collector agent on them. The agent installer is completely **cross-distro** (supports Ubuntu, Debian, CentOS, RHEL, Fedora, Arch, Alpine, etc.) and guarantees **Zero-Impact** to your production workloads.

1. Open your Auditd GUI Dashboard and navigate to the **Servers** page.
2. Click **Install Agent** in the top right corner.
3. Choose your preferred installation mode:
   - **Docker**: Runs the agent in an isolated container.
   - **Native (Standalone/ZIP)**: Creates a strictly isolated Python `venv` with hard CPU/RAM limits via Systemd. Never upgrades your system packages.
4. Copy the secure 1-line installation command (which includes your auto-generated API Token).
5. SSH into your target server and run the command. Within seconds, the new server will appear on your dashboard!

## 📖 How to Use

### 🖥️ Dashboard
The main dashboard gives you a bird's-eye view of your infrastructure. Monitor active SSH sessions, view daily command counts, and spot recent security alerts at a glance.

### 👤 Sessions
Navigate to the **Sessions** tab to see exactly who logged in and when. Click on any session to drill down into a timeline of **every single command** executed during that specific session.

### ⚠️ Alerts
The **Alerts** tab categorizes security events by severity. You can customize the thresholds (e.g., how many failed logins trigger a Brute Force alert) directly in the **Settings** UI or via the `.env` file.

## 🔒 Security Best Practices

> **[WARNING]**  
> Auditd GUI processes highly sensitive system data. If you are deploying this in a production environment, you **MUST** follow these practices:

1. **Change Default Credentials**: Update the `ADMIN_PASSWORD` in your `.env` file immediately after installation.
2. **Secure Node Communication**: The `install.sh` script automatically generates a secure `NODE_API_KEY`. Never share this key publicly.
3. **Use HTTPS (Reverse Proxy)**: Never expose ports `7432` (Web) or `7433` (API) directly to the public internet. Place Auditd GUI behind a reverse proxy like **Nginx, Caddy, or Traefik** with an SSL/TLS certificate (e.g., Let's Encrypt).
4. **Firewall Rules**: Restrict port access. Only allow your collector nodes' IP addresses to communicate with the API port.

## ⚙️ Configuration

You can fine-tune data retention and alert sensitivities directly in the **Settings** tab of the Web Dashboard. Changes take effect immediately without requiring a server restart.

*Note: The `.env` file is now strictly used for core runtime parameters like ports, log paths, and cryptographic keys.*

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report bugs, and suggest features. Be sure to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## 📄 License

This project is licensed under the [MIT License](LICENSE).
