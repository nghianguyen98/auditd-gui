# Security Policy

## Supported Versions

Currently, only the latest version of Auditd GUI is supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within Auditd GUI, please DO NOT open a public issue. Instead, please send an e-mail to the repository maintainer directly or use GitHub's private vulnerability reporting feature.

All security vulnerabilities will be promptly addressed.

### Best Practices for Users
- Always change the default `ADMIN_PASSWORD` in `.env`.
- Ensure `NODE_API_KEY` is a strong random secret.
- Do not expose ports 7432 or 7433 to the public internet without a reverse proxy providing SSL/TLS and proper authentication.
