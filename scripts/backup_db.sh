#!/bin/bash
# On-demand database backup — for use before a risky migration or deploy,
# in addition to (not instead of) the automated daily backup.
#
# The automated backup runs once a day at 04:00 via
# /srv/hbrl/scripts/backup_hbrl_db.sh (shared with other HardbanRecordsLab
# services on this box, cron entry already installed — this app's database
# was added to its DATABASES list as part of this change). 7-day retention,
# stored in /srv/hbrl/backups/.
#
# Usage (on the VPS): ./scripts/backup_db.sh
set -euo pipefail

CONTAINER="hbrl-postgres"
DB="ai_publish_engine"
DB_USER="hbrl_admin"
BACKUP_DIR="/srv/hbrl/backups"
DATE="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/${DB}_manual_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "Backing up $DB -> $OUT"
docker exec -t "$CONTAINER" pg_dump -U "$DB_USER" "$DB" | gzip > "$OUT"
gzip -t "$OUT" && echo "OK: $(du -h "$OUT" | cut -f1)"

# Restore from any backup produced by this script or the daily cron job:
#   zcat /srv/hbrl/backups/ai_publish_engine_<timestamp>.sql.gz | \
#     docker exec -i hbrl-postgres psql -U hbrl_admin ai_publish_engine
