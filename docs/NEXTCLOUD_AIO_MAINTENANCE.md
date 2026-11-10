# Nextcloud AIO — task 1B

Depends on host-maintenance v1 (PR #142). Initial observed installation:
Nextcloud 33.0.7, AIO mastercontainer, PostgreSQL managed by AIO,
`/srv/nas/Dati/drive/nextcloud` mounted at `/mnt/ncdata`.
The owner reported a successful initial AIO backup configured at
`/srv/backups/nextcloud-aio`. A restore has NOT been tested. Data and backup
are on the same physical disk; this protects an update workflow, not disk failure.

## Activation after review and host installation

Preserve the other settings in `/srv/cora-tools/updater/config.json` and set
`managed_apps_enabled` and `nextcloud_aio_enabled` to `true`, then restart the
updater during an idle maintenance window. No passwords or Borg keys are copied
to Cora. The existing installation is managed, never installed or recreated by Cora.
The UI under Gestisci applicazioni offers Backup e aggiorna Nextcloud.

## Contract

- Requires healthy AIO, no active backup/restore and no AIO daily script lock.
- Calls the official `/daily-backup.sh` with explicit backup-only flags first.
- A successful script exit alone is insufficient: Borg must have a new FinishedAt,
  exit code zero and be stopped; AIO must be healthy again before update starts.
- Then invokes AIO's automatic update mode. Only a changed, healthy mastercontainer
  permits one continuation after a master update. Arbitrary failures are not retried.
- Verifies core containers and `occ status` (installed, no maintenance, no pending
  database upgrade), and records before/after versions and backup completion time.
- Jobs survive Cora restarts. Host updater restart during work becomes
  recovery_required; no background replay occurs. Concurrent managed operations
  and host lifecycle changes are blocked while Nextcloud is running/recovery_required.
- Timeouts stop the local Docker client, not necessarily work already running in AIO.
  A recovery_required result therefore requires inspecting AIO before further action.

## Recovery

No automatic database restore or image downgrade is attempted. Open the AIO panel
at https://serverale:8080 and inspect the actual job. Complete recovery there using
AIO Backup and restore if needed. Preserve the Borg password privately. After checking
files/access and the AIO outcome, click Conferma recupero verificato in Cora. This
rechecks health, absence of running backup/restore and lock; it only acknowledges
operator recovery, and never runs an update or claims a restore test has passed.

Do not run simultaneous updates from AIO and Cora. Coordination with AIO's independent
scheduler is best-effort preflight, not a shared atomic lock. Keep AIO scheduled
maintenance outside the manual update window.

## Remaining real-server acceptance

Confirm feature activation, refresh-only behavior, successful backup/update through
Cora, persistence across reload and accurate version. Test restore and interrupted
updates on a disposable AIO instance before declaring recovery certified. Local tests
use simulated Docker responses and do not certify the server's backup contents.

Official interfaces reviewed:
https://github.com/nextcloud/all-in-one#how-to-stopstartupdate-containers-or-trigger-the-daily-backup-from-a-script-externally
https://github.com/nextcloud/all-in-one/blob/main/Containers/mastercontainer/daily-backup.sh
