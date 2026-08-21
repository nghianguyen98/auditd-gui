# Contributing to Auditd GUI

First off, thank you for considering contributing to Auditd GUI! It's people like you that make open source such a great community.

## How to Contribute

### Reporting Bugs
- Ensure the bug was not already reported by searching on GitHub under Issues.
- If you're unable to find an open issue addressing the problem, open a new one. Be sure to include a title and clear description, as much relevant information as possible, and a code sample or an executable test case demonstrating the expected behavior that is not occurring.

### Suggesting Enhancements
- Open a new issue with a clear title and description of your enhancement.
- Explain why this enhancement would be useful to most users.

### Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. Ensure the test suite passes.
4. Make sure your code lints.
5. Issue that pull request!

## Local Development Environment

You can spin up a local development environment using Docker Compose:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```
This will mount `./dev-mock/` for mock logs, so you don't need a real `auditd` running on your host machine to test the UI and API parsing.
