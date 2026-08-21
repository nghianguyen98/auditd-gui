# Auditd GUI 🛡️

Auditd GUI is a comprehensive, centralized Linux Activity Monitor built with a modern web interface. It parses system `auditd` and `auth.log` data to provide realtime insights into SSH sessions, executed commands, and security alerts across multiple servers.

![Auditd GUI Logo](web/public/favicon.svg)

## Features

- **Multi-Node Monitoring**: Connect and monitor multiple Linux servers from a single pane of glass.
- **Activity & Session Tracking**: Trace every user session, including exact commands executed, even after `sudo -i` escalations.
- **Automated Security Alerts**: Out-of-the-box detection for:
  - SSH Brute Force attempts
  - Sudo Privilege Escalations
  - Mass File Deletions
  - Suspicious Commands
  - Sensitive File Access
- **Modern Glassmorphism UI**: Beautiful React-based interface with automatic Dark/Light mode switching.
- **Lightweight Collector**: Agent written in pure Python, reading `auditd` logs efficiently without heavy JVM dependencies.
- **Dockerized**: Easy deployment via `docker-compose`.

## Architecture

```text
[ Linux Server (Node 1) ] 
  - auditd (kernel audit) 
  - /var/log/audit/audit.log 
  - /var/log/auth.log
        |
    [ Python Collector Agent ]  -- REST API -->  [ Central Auditd GUI Server ]
                                                      - FastAPI (Backend)
                                                      - SQLite (Database)
                                                      - React/Vite (Frontend)
```

## Quick Start (Docker)

1. Clone this repository:
```bash
git clone https://github.com/nghianguyen98/auditd-gui.git
cd auditd-gui
```

2. Run the automated installer script:
```bash
sudo bash install.sh
```

> **Note:** The `install.sh` script automatically installs `auditd`, configures production-safe log rotation, sets up your `.env` variables, and starts the Docker containers.

3. Access the Web UI:
Open `http://<your-server-ip>:7432` in your browser. 
Login with the default credentials: `admin` / `ChangeMe@2024!` 
*(Ensure you update this password in your `.env` file immediately!)*

## Manual Installation (Adding Nodes)

To add another server (node) to your central Auditd GUI dashboard, run the agent on the target server.

### 1. Generate an Installer Command
On the Auditd GUI dashboard, go to the **Servers** page. At the top right, you will see a script to curl the installer directly from your API server.

### 2. Run on Target Node
```bash
curl -s http://<CENTRAL_IP>:7433/nodes/install-script | sudo bash
```
*This script will deploy the `auditvisual-collector` container pointing back to your central server.*

## Security Best Practices

> **[WARNING]**  
> Auditd GUI processes sensitive system data. You MUST follow these practices for a production environment:

1. **Change Default Passwords**: Update `ADMIN_PASSWORD` in `.env` immediately.
2. **Secure Node Communication**: Ensure `NODE_API_KEY` in `.env` is a strong, random string (the `install.sh` script generates one automatically).
3. **Use HTTPS**: Never expose the Web UI or API directly to the internet without a reverse proxy (like Nginx, Caddy, or Traefik) providing SSL/TLS encryption.
4. **Firewall Rules**: Block public access to port `7432` and `7433`. Only allow trusted IP addresses.

## Configuration (`.env`)

You can toggle alerts and adjust thresholds directly in the `.env` file located at the root of this project:

```env
# Alert thresholds
BRUTE_FORCE_COUNT=5
BRUTE_FORCE_WINDOW_MIN=5

MASS_DELETE_COUNT=10
MASS_DELETE_WINDOW_SEC=60
```
After modifying `.env`, restart the backend:
```bash
docker compose restart api
```

## Development

If you'd like to develop or test locally without a real `auditd` setup (e.g., on macOS or Windows):

1. Start the stack with the `dev` override:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
2. The `dev` override mounts mock log files from `./dev-mock/` instead of system paths.
3. Access the frontend at `http://localhost:7432`.

## Contributing

Pull requests are welcome! Please ensure that your code adheres to the existing formatting and structure.

## License

This project is licensed under the MIT License.
