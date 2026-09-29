#!/bin/sh
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="/backups/freelance_db_$TIMESTAMP.sql.gz"

echo "Creating backup $BACKUP_FILE..."
pg_dump -h db -U freelance -d freelance | gzip > "$BACKUP_FILE"

if [ -n "$S3_BUCKET" ]; then
  echo "Uploading to S3..."
  # Assuming aws-cli is installed in the container
  aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/db_backups/"
fi

# Keep only the last 7 days of backups locally
find /backups -type f -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed successfully."
