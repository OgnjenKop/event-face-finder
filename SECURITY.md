# Security Policy

## Supported Versions

Event Face Finder is pre-1.0 software. Security fixes are handled on the `main` branch
until versioned releases are established.

## Reporting A Vulnerability

Please report security or privacy-sensitive issues privately. You can use the "Report a vulnerability" button on the **Security** tab of the GitHub repository, or email the maintainers at `ognjen.koprivica@live.com`. Do not open a public issue for security concerns.

Examples of sensitive reports include:

- A path traversal or arbitrary file read/write issue.
- A way for the local GUI to expose files outside generated outputs.
- Unsafe handling of reference photos, embeddings, caches, or match results.
- Dependency vulnerabilities that affect local execution.

When reporting, include:

- A short description of the issue.
- Steps to reproduce with synthetic data.
- Your operating system and Python version.
- Any relevant logs with private paths, faces, and embeddings removed.

Do not attach real event photos, face crops, embeddings, or cache databases unless a
maintainer explicitly requests a sanitized sample.

## Local GUI Scope

The GUI is intended for local use on `127.0.0.1`. Do not expose it to untrusted networks.
It can start local scans and read generated contact sheets, so treat it as a local tool,
not as a hosted web application.
