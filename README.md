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

## 🚀 Quick Start (Central Server)

Setting up your central dashboard takes less than a minute. The server runs completely inside Docker, meaning it is **100% cross-platform** and runs on any Linux distribution.

### Prerequisites
- `docker` and `docker-compose` (or `docker compose`) installed on the host.

### 1. Clone & Install
Run this on the server you want to act as your **Central Dashboard**:
```bash
git clone https://github.com/nghianguyen98/auditd-gui.git
cd auditd-gui
sudo bash install.sh
```
> 💡 **What does `install.sh` do?** It automatically configures `auditd` rules, sets up secure `.env` credentials, generates cryptographic keys, and launches the Docker containers.

### 2. Login
1. Open your browser and navigate to `http://<your-server-ip>:7432`
2. Login with the default credentials:
   - **Username**: `admin`
   - **Password**: `ChangeMe@2024!` *(Ensure you update this immediately!)*

## 📡 Adding Nodes (Monitoring Other Servers)

To monitor additional servers, you just need to install the lightweight collector agent on them. The agent installer is completely **cross-distro** (supports Ubuntu, Debian, CentOS, RHEL, Fedora, Arch, Alpine, etc.) and auto-detects your package manager (`apt`, `yum`, `dnf`, `pacman`, `zypper`, `apk`).

1. Open your Auditd GUI Dashboard and navigate to the **Servers** page.
2. Click **Install Agent** in the top right corner.
3. The system will generate a secure, unique **Per-Node API Token** and a 1-line installation script.
4. SSH into your target server and run that script.
5. Within seconds, the new server will appear on your dashboard!

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

## ⚙️ Configuration (`.env`)

You can fine-tune data retention and alert sensitivities in the `.env` file:

```env
# How many days to keep logs (0 = keep forever)
LOG_RETENTION_DAYS=90

# Brute force threshold: 5 failed attempts within 5 minutes
BRUTE_FORCE_COUNT=5
BRUTE_FORCE_WINDOW_MIN=5

# Mass delete threshold: 10 files deleted within 60 seconds
MASS_DELETE_COUNT=10
MASS_DELETE_WINDOW_SEC=60
```
*(Remember to run `docker compose restart api` after modifying `.env`)*

## 🛠️ Local Development

Want to test the UI locally without a real `auditd` setup (e.g., on macOS or Windows)?

1. Start the stack with the `dev` override:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
2. The `dev` override mounts mock log files from `./dev-mock/` instead of your real system paths.
3. Access the frontend at `http://localhost:7432`.

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report bugs, and suggest features. Be sure to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## 📄 License

This project is licensed under the [MIT License](LICENSE).
