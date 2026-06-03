# Security Policy

## Supported Versions

We actively maintain security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.4.x   | :white_check_mark: |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue,
please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities.

2. **Email the maintainers directly** at the email address listed in the
   repository or through GitHub's private vulnerability reporting feature.

3. **Include the following information:**
   - A description of the vulnerability
   - Steps to reproduce the issue
   - Potential impact assessment
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours.
- **Assessment**: We will investigate and assess the vulnerability within 7 days.
- **Resolution**: We aim to provide a fix within 30 days for critical issues.
- **Disclosure**: We will coordinate with you on public disclosure timing.

### Security Best Practices for Users

When using ddigraph in production:

1. **Credentials Management**
   - Never commit Neo4j credentials to version control
   - Use environment variables (`DDIGRAPH_NEO4J_*`) for sensitive configuration
   - Rotate credentials regularly

2. **Network Security**
   - Use TLS/SSL for Neo4j connections (`neo4j+s://` or `bolt+s://`)
   - Configure `encrypted=True` in settings for secure connections
   - Restrict database access to authorized hosts only

3. **Input Validation**
   - Validate XML files before processing
   - Use `strict_parsing=True` for untrusted input
   - Monitor for unusually large or malformed files

4. **Dependency Updates**
   - Keep ddigraph and its dependencies up to date
   - Monitor security advisories for lxml, neo4j, and other dependencies
   - Use `pip-audit` or similar tools for vulnerability scanning

## Security Features

ddigraph includes several security-conscious features:

- **Pydantic validation** for all configuration settings
- **SecretStr** for password fields (prevents accidental logging)
- **Path validation** before file operations
- **Streaming XML parsing** to handle large files safely
- **Configurable TLS** for encrypted database connections

## Acknowledgments

We appreciate the security research community's efforts in helping keep
ddigraph secure. Contributors who report valid security issues will be
acknowledged in our release notes (unless they prefer to remain anonymous).
