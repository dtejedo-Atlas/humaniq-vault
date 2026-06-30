#!/bin/bash
# Daily MongoDB Backup Script
# Run at 2:00 AM daily via cron

SCRIPT_DIR="/app/backend/scripts"
LOG_FILE="/var/log/mongodb_backup.log"
PYTHON_PATH="/root/.venv/bin/python"

echo "========================================" >> $LOG_FILE
echo "Backup started at $(date)" >> $LOG_FILE
echo "========================================" >> $LOG_FILE

cd /app/backend
$PYTHON_PATH $SCRIPT_DIR/backup_mongodb.py >> $LOG_FILE 2>&1

echo "Backup completed at $(date)" >> $LOG_FILE
echo "" >> $LOG_FILE
