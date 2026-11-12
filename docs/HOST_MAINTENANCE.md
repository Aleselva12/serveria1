# Host maintenance v1 — task 1A

This change concerns the updater only. Nextcloud and worker evidence are separate tasks.

The owner-only one-shot verification flow compares an SHA-256 digest of updater Python
sources with the installed host package. An identical digest skips the update even when
unrelated Cora files changed. Otherwise the authenticated bridge accepts only the active
Cora commit recorded by the host. Candidate bytes come from that commit in the existing
host Git repository; the browser cannot provide a URL, path, script or arbitrary ref.

The installed updater stages and syntax-checks the package, excludes concurrent updater
and managed-app jobs, and writes a fixed request. A standalone systemd helper running as
`ale` stops the updater, saves `maintenance.previous`, replaces `installed`, starts the
service and checks the authenticated maintenance endpoint and exact digest. Failure
restores the previous package. A durable journal records rename intent: an interrupted
switch is rolled back on the next helper invocation. Failed recovery keeps the request
and journal, reports `recovery_required` and blocks new writes. Configuration, credentials,
application state, database and release jobs remain outside the replaced package.

Besides this owner-requested alignment, an `apply` job hands off to the updater
package of the release it is about to install, before stopping Cora (see
`updater/README.md`). The request then carries `handoff_job`; the candidate bytes
still come only from the host Git repository, now from the commit of a `ready`
release being applied. The engine never hands off twice for the same job, so a
helper rollback cannot loop.

The switch uses two directory renames while the service is stopped, not a live directory
swap. Process-interruption recovery is tested; power-loss/filesystem durability and real
systemd behavior still require the Debian acceptance test. The previous directory is a
single-generation code rollback, not a data backup or a manual rollback API.

## Initial installation on ServerAle

Confirmed service: user `ale`, root `/srv/cora-tools/updater`, working directory
`/srv/cora-tools/updater/installed`. Other layouts are deliberately rejected.

From a trusted checkout containing this change, during a maintenance window with no
application updates/backups in progress:

```sh
sudo python3 -m updater.install_maintenance
```

This is a one-time provisioning operation, NOT something to run before review/merge.
It installs the helper under `/usr/local/lib`, two systemd units, and a sudoers rule
allowing `ale` exactly `systemctl stop/start cora-updater.service`. It preserves the old
package as `bootstrap.previous`. Later package updates need no sudo prompt. The helper
itself is deliberately not self-updated: changes to its protocol require a reviewed host
installation. No new network listener or third container is introduced.

Do not run the installer from inside `installed`. Existing bootstrap artifacts or helper
configuration cause refusal rather than overwrite. If installation fails, inspect its
error and service state before retrying; do not delete backups merely to bypass a refusal.

## Acceptance on Debian (not yet executed)

1. Check `systemctl is-active cora-updater.service cora-host-maintenance.path`.
2. Run one-shot checks with matching versions: no restart should occur.
3. Deploy a release changing updater Python sources, then run one-shot checks: observe
   prerequisite update, exact version health and subsequent check results.
4. In a disposable installation, inject a candidate startup failure and interrupt the
   helper between renames; verify previous service, credentials and jobs remain intact.
5. Verify pending jobs refuse maintenance and that recovery failure blocks writes.

For recovery diagnostics use `journalctl -u cora-host-maintenance.service` and the files
`maintenance.result.json` / `maintenance.journal.json` in the updater root. Never paste
`bridge.token` or configuration secrets into chat. Keep the helper path unit stopped
while an operator repairs a `recovery_required` condition.
