#!/bin/sh
# Nightly backup of the database and all photos. Cron:
#   30 2 * * * /srv/spectrum/Spectrum-backend/deploy/backup.sh
#
# Without S3 the originals exist only on this disk, so copy them OFF the server:
# set BACKUP_REMOTE (e.g. user@backup-host:/backups/spectrum or an rclone remote path).
set -eu
DATA=/srv/spectrum/data
MEDIA=/srv/spectrum/media
BACKUPS=/srv/spectrum/backups
mkdir -p "$BACKUPS"

# Consistent SQLite copy while the site is running.
sqlite3 "$DATA/db.sqlite3" ".backup $BACKUPS/db-$(date +%F).sqlite3"
find "$BACKUPS" -name 'db-*.sqlite3' -mtime +14 -delete

if [ -n "${BACKUP_REMOTE:-}" ]; then
    # Incremental: only new or changed photos are sent. Originals first, they can't be recreated.
    rsync -a "$MEDIA/private/" "$BACKUP_REMOTE/media/private/"
    rsync -a "$MEDIA/public/" "$BACKUP_REMOTE/media/public/"
    rsync -a "$BACKUPS/" "$BACKUP_REMOTE/db/"
fi
