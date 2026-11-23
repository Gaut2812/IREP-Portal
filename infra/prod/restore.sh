#!/usr/bin/env bash
# Restore an ENCRYPTED backup made by backup.sh, then record the restore (the restore drill) in
# $BACKUP_DIR/restore-drills.log, which golive_check reads.
#
#   sudo ./restore.sh /var/backups/irep/2026-11-20_0215 /root/irep-backup.key
#
# The private key (age identity) comes from your password manager; copy it to the server only for the
# restore, and delete it afterwards: shred -u /root/irep-backup.key
# This REPLACES the portal and Keycloak databases and the uploads with the backup. See DEPLOY.md.
set -euo pipefail

BACKUP="${1:?usage: restore.sh <backup folder> <age key file>}"
KEY="${2:?usage: restore.sh <backup folder> <age key file>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
envget() { { grep -E "^$1=" .env || true; } | tail -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/; s/[[:space:]]+$//'; }
BACKUP_DIR="$(envget BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/var/backups/irep}"
command -v age >/dev/null || { echo "age is not installed: sudo apt-get install -y age" >&2; exit 2; }
test -r "$KEY" || { echo "cannot read the key file $KEY" >&2; exit 2; }
for f in irep.dump.age keycloak.dump.age uploads.tar.gz.age SHA256SUMS; do
  test -s "$BACKUP/$f" || { echo "$BACKUP/$f is missing: is this an encrypted backup folder?" >&2; exit 2; }
done
( cd "$BACKUP" && sha256sum -c --quiet SHA256SUMS ) || { echo "checksums do not match: the backup is damaged" >&2; exit 1; }
dec() { age -d -i "$KEY" "$BACKUP/$1"; }
# prove the key opens every file (and that none was tampered with) before anything is stopped or replaced
for f in irep.dump.age keycloak.dump.age uploads.tar.gz.age; do
  dec "$f" >/dev/null || { echo "the key does not decrypt $f" >&2; exit 1; }
done

dc() { docker compose "$@"; }
echo "[$(date -Is)] restoring $BACKUP"
dc stop api worker beat web keycloak
dec irep.dump.age | dc exec -T postgres pg_restore -U irep -d irep --clean --if-exists --no-owner
dec keycloak.dump.age | dc exec -T postgres pg_restore -U irep -d keycloak --clean --if-exists --no-owner --role=keycloak
dec uploads.tar.gz.age | dc run --rm --no-deps -T -u 0 --entrypoint sh api \
  -c 'find /data/uploads -mindepth 1 -delete && tar -xzf - -C /data/uploads && chown -R 10001:10001 /data/uploads'
dc up -d

mkdir -p "$BACKUP_DIR"
printf '{"at": "%s", "backup": "%s", "host": "%s", "kind": "restore"}\n' "$(date -Is)" "$(basename "$BACKUP")" "$(hostname)" \
  >> "$BACKUP_DIR/restore-drills.log"
echo "[$(date -Is)] restored and recorded in $BACKUP_DIR/restore-drills.log; now delete the key: shred -u $KEY"
