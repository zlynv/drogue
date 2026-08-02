# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.2.x   | :white_check_mark: |
| 0.1.x   | :x:                |
| < 0.1   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in drogue, please report it responsibly.

**Do not** open a public GitHub issue for security bugs.

### How to Report

1. Go to [GitHub's private vulnerability reporting](https://github.com/zlynv/drogue/security/advisories/new)
2. Provide a detailed description of the vulnerability
3. Include steps to reproduce the issue
4. Describe the potential impact

### What to Include

- **Description**: What is the vulnerability?
- **Reproduction steps**: How can it be triggered?
- **Impact**: What could an attacker achieve?
- **Suggested fix** (optional): If you have a recommendation

### Response Timeline

| Action | Timeline |
|--------|----------|
| Acknowledgment | 48 hours |
| Initial assessment | 1 week |
| Fix or mitigation | 2 weeks (critical), 1 month (non-critical) |
| Public disclosure | After fix is released |

### Scope

**In scope:**
- Rate limiting bypass vulnerabilities
- DDoS detection evasion
- Header spoofing attacks
- Storage backend vulnerabilities (Redis, MongoDB)
- Authentication/authorization issues in drogue code
- Dependency vulnerabilities

**Out of scope:**
- Vulnerabilities in your application code
- Issues in third-party dependencies (report to upstream)
- Social engineering attacks
- Physical attacks

## Safe Harbor

We support safe harbor for security researchers who:

- Make a good faith effort to avoid privacy violations and data destruction
- Only interact with accounts you own or with explicit permission
- Do not exploit a vulnerability beyond what is necessary to confirm it exists
- Report promptly and do not publicly disclose until a fix is available

We will not pursue legal action against researchers who follow these guidelines.

## Security Best Practices

When using drogue in production:

1. **Use HTTPS** — Always encrypt traffic in transit
2. **Configure trusted proxies** — Prevent header spoofing
3. **Use Redis/MongoDB authentication** — Secure storage backends
4. **Monitor rate limit metrics** — Watch for anomalies
5. **Keep drogue updated** — Apply security patches promptly

## Contact

For non-security issues, use [GitHub Issues](https://github.com/zlynv/drogue/issues).

For security concerns, use [Private Vulnerability Reporting](https://github.com/zlynv/drogue/security/advisories/new).
