#!/bin/sh
set -e

# Wait for DB to be ready
echo "Waiting for database..."
until pg_isready -h db -U freelance -d freelance; do
  sleep 2
done

# Run cron in the foreground
echo "Starting cron for database backups..."
crond -f -l 2
