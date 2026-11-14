# Security Policy

Cora Lab is a self-hosted, single-owner project under active development.
It is not currently designed for direct exposure to the public Internet or
untrusted multi-user environments.

## Reporting a vulnerability

Please **do not** publish credentials, private infrastructure details,
exploit instructions, or personal information in a public GitHub issue.

Use GitHub's private vulnerability reporting feature if it is enabled for
this repository. Otherwise, contact the maintainer privately through an
available channel on their GitHub profile. Provide a concise description,
affected version or commit, reproducible steps, and potential impact
without including real secrets.

Security reports are reviewed on a best-effort basis. No fixed response
or remediation timeline is promised.

## Deployment precautions

- Restrict access to a trusted network (for example Tailscale) and HTTPS.
- Keep the API, database, updater, worker, and terminal service off the
  public Internet unless they have been independently reviewed and hardened.
- Keep `.env`, `deploy.env`, OAuth credentials, keys, tokens, private logs,
  backups, and real customer/user data out of version control.
- Use distinct strong credentials for each deployment; never reuse
  example passwords or placeholder tokens.
- Limit filesystem mounts and privileges; do not mount the Docker socket
  into an application container without an explicit security design.
- Rotate exposed credentials immediately. Removing them from a recent
  commit alone does **not** remove them from Git history.
- Use disposable test databases; follow documented backup, verification,
  and rollback procedures before changing production deployments.

## Scope of public-source review

Security checks of repository contents cannot verify the configuration of
an installed host or guarantee the absence of historical secrets. Deployers
must review their own infrastructure, dependencies, and authentication
boundaries before exposing any service.
