#!/usr/bin/env bash
# Nightly backup: both Postgres databases (app + Keycloak) and the uploads volume.
# Keeps BACKUP_KEEP_DAYS (7) days locally and copies each night's set to BACKUP_REMOTE when set.
#
#   sudo /opt/irep/infra/prod/backup.sh                  # run once by hand first
#   cron (root):  15 2 * * * /opt/irep/infra/prod/backup.sh >> /var/log/irep-backup.log 2>&1
#
# Restore: docs/deploy/DEPLOY.md, "Restore from a backup".
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
# read single keys from .env (not `source`: values may hold spaces and <>)
envget() { { grep -E "^$1=" .env || true; } | tail -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/; s/[[:space:]]+$//'; }
BACKUP_DIR="$(envget BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/var/backups/irep}"
KEEP="$(envget BACKUP_KEEP_DAYS)"; KEEP="${KEEP:-7}"
BACKUP_REMOTE="$(envget BACKUP_REMOTE)"
STAMP="$(date +%Y-%m-%d_%H%M)"
OUT="$BACKUP_DIR/$STAMP"
umask 077
mkdir -p "$OUT"

dc() { docker compose "$@"; }          # run from this folder: picks up docker-compose.yml and .env

echo "[$(date -Is)] backup to $OUT"
# -Fc: compressed custom format, restored with pg_restore
dc exec -T postgres pg_dump -U irep -d irep -Fc > "$OUT/irep.dump"
dc exec -T postgres pg_dump -U irep -d keycloak -Fc > "$OUT/keycloak.dump"
# uploads: certificate proofs, exports, report and card PDFs (read-only mount, nothing stopped)
dc run --rm --no-deps -T -u 0 -v "$OUT:/backup" --entrypoint tar api -czf /backup/uploads.tar.gz -C /data/uploads .
( cd "$OUT" && sha256sum irep.dump keycloak.dump uploads.tar.gz > SHA256SUMS )

for f in irep.dump keycloak.dump uploads.tar.gz; do
  test -s "$OUT/$f" || { echo "backup file $f is empty" >&2; exit 1; }
done

# keep KEEP days locally
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +"$((KEEP - 1))" -exec rm -rf {} +

# second location
if [ -n "${BACKUP_REMOTE:-}" ]; then
  case "$BACKUP_REMOTE" in
    *@*:*) rsync -a --delete "$BACKUP_DIR/" "$BACKUP_REMOTE/" ;;   # ssh host: mirror of the last KEEP days
    *)     rclone sync "$BACKUP_DIR" "$BACKUP_REMOTE" ;;             # rclone remote (B2, R2, Drive...): same mirror
  esac
  echo "[$(date -Is)] copied to $BACKUP_REMOTE"
fi
echo "[$(date -Is)] done: $(du -sh "$OUT" | cut -f1)"
