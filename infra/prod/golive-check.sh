#!/usr/bin/env bash
# Pre-go-live checklist (apps/api/ops/golive_check.py). Exit 1 until every check passes:
# Keycloak bootstrap admin gone, no default secrets, no demo data, encrypted backups, a recorded restore.
#
#   cd /opt/irep/infra/prod && sudo ./golive-check.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
envget() { { grep -E "^$1=" .env || true; } | tail -n1 | cut -d= -f2- | sed -E 's/[[:space:]]+#.*$//; s/^"(.*)"$/\1/; s/[[:space:]]+$//'; }
BACKUP_DIR="$(envget BACKUP_DIR)"; BACKUP_DIR="${BACKUP_DIR:-/var/backups/irep}"
mkdir -p "$BACKUP_DIR"
docker compose run --rm -T -v "$BACKUP_DIR:/backups:ro" api python ops/golive_check.py --backups /backups
