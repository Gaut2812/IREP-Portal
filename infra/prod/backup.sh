#!/usr/bin/env bash
# Nightly ENCRYPTED backup: both Postgres databases (app + Keycloak) and the uploads volume.
# Every file is encrypted with age (https://age-encryption.org, open source) to BACKUP_AGE_RECIPIENT
# while it is written: plain data never touches the disk, and only encrypted files leave the server.
# The matching private key is NOT on this server (docs/deploy/DEPLOY.md, "Backup key").
# Keeps BACKUP_KEEP_DAYS (7) days locally and mirrors them to BACKUP_REMOTE when set.
#
#   sudo /opt/irep/infra/prod/backup.sh                  # run once by hand first
#   cron (root):  15 2 * * * /opt/irep/infra/prod/backup.sh >> /var/log/irep-backup.log 2>&1
#
# Restore: infra/prod/restore.sh (needs the private key), see DEPLOY.md "Restore from a backup".
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
# read single keys from .env (not `source`: values may hold spaces and <>)
envget() { { grep -E "^$1=" .env || true; } | tail -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/; s/[[:space:]]+$//'; }
BACKUP_DIR="$(envget BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/var/backups/irep}"
KEEP="$(envget BACKUP_KEEP_DAYS)"; KEEP="${KEEP:-7}"
BACKUP_REMOTE="$(envget BACKUP_REMOTE)"
RECIPIENT="$(envget BACKUP_AGE_RECIPIENT)"

# refuse to write anything unencrypted
case "$RECIPIENT" in
  age1*) ;;
  *) echo "BACKUP_AGE_RECIPIENT is not set to an age public key (age1...): refusing to write an unencrypted backup." >&2
     echo "Create the key pair on your own computer (DEPLOY.md, 'Backup key') and put only the public key in .env." >&2
     exit 2 ;;
esac
command -v age >/dev/null || { echo "age is not installed: sudo apt-get install -y age" >&2; exit 2; }

STAMP="$(date +%Y-%m-%d_%H%M)"
OUT="$BACKUP_DIR/$STAMP"
umask 077
mkdir -p "$OUT"
enc() { age -r "$RECIPIENT" -o "$1"; }   # stdin -> encrypted file

dc() { docker compose "$@"; }          # run from this folder: picks up docker-compose.yml and .env

echo "[$(date -Is)] encrypted backup to $OUT"
# -Fc: compressed custom format, restored with pg_restore
dc exec -T postgres pg_dump -U irep -d irep -Fc | enc "$OUT/irep.dump.age"
dc exec -T postgres pg_dump -U irep -d keycloak -Fc | enc "$OUT/keycloak.dump.age"
# uploads: certificate proofs, recordings, exports, report and card PDFs (read-only, nothing stopped)
dc run --rm --no-deps -T -u 0 --entrypoint tar api -czf - -C /data/uploads . | enc "$OUT/uploads.tar.gz.age"
( cd "$OUT" && sha256sum irep.dump.age keycloak.dump.age uploads.tar.gz.age > SHA256SUMS )

for f in irep.dump.age keycloak.dump.age uploads.tar.gz.age; do
  test -s "$OUT/$f" || { echo "backup file $f is empty" >&2; exit 1; }
  head -c 21 "$OUT/$f" | grep -q "age-encryption.org/v1" || { echo "backup file $f is not age-encrypted" >&2; exit 1; }
done
echo "$RECIPIENT" > "$OUT/RECIPIENT"           # which public key; the private key decrypts all files

# keep KEEP days locally
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$((KEEP - 1))" -exec rm -rf {} +

# second location: encrypted files only (plus the restore-drill log)
if [ -n "${BACKUP_REMOTE:-}" ]; then
  case "$BACKUP_REMOTE" in
    *@*:*) rsync -a --delete "$BACKUP_DIR/" "$BACKUP_REMOTE/" ;;   # ssh host: mirror of the last KEEP days
    *)     rclone sync "$BACKUP_DIR" "$BACKUP_REMOTE" ;;             # rclone remote (B2, R2, Drive...): same mirror
  esac
  echo "[$(date -Is)] copied to $BACKUP_REMOTE"
fi
echo "[$(date -Is)] done: $(du -sh "$OUT" | cut -f1)"
