# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions,
or pull requests.**

Instead, report privately through either:

- **GitHub Security Advisories** — use the "Report a vulnerability" button under the
  repository's **Security** tab (preferred), or
- **Email** — nmamizerov@gmail.com

Please include:

- A description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept if possible).
- Affected version / commit and configuration (e.g. `BILLING_ENABLED`, queue tier on/off).

## What to expect

- **Acknowledgement** within 5 business days.
- An initial assessment and severity rating shortly after.
- Coordinated disclosure: we'll agree on a timeline and credit you (if you wish) once a
  fix is released.

## Supported versions

This project is pre-1.0; security fixes are applied to the `main` branch and the latest
release. Please test against `main` before reporting.

## Scope notes

- Self-hosting defaults are security-conscious: the backend **fails fast** without a valid
  `JWT_SECRET_KEY` and `ENCRYPTION_KEY`, the HTTP-request node blocks private/link-local
  targets unless `HTTP_NODE_ALLOW_INTERNAL=true`, and billing/payment endpoints are off by
  default (`BILLING_ENABLED=false`).
- When reporting, please state whether you changed any of these defaults.
