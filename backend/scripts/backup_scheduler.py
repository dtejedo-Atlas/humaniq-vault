#!/usr/bin/env python3
"""
MongoDB Backup Scheduler for Humaniq Talent Vault
Runs daily backups at a specified time and logs results.

This script runs as a background service managed by supervisor.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, '/app/backend')
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

# Configuration
BACKUP_HOUR_UTC = 3  # 3:00 AM UTC
LOG_FILE = Path("/var/log/mongodb_backup.log")
STATUS_FILE = Path("/app/backups/last_backup_status.json")
BACKUP_SCRIPT = Path("/app/backend/scripts/backup_mongodb.py")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_backup():
    """Execute the backup script and return success status."""
    import subprocess
    
    logger.info("=" * 50)
    logger.info("Starting scheduled backup...")
    
    try:
        result = subprocess.run(
            ['/root/.venv/bin/python', str(BACKUP_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd='/app/backend'
        )
        
        if result.returncode == 0:
            logger.info("Backup completed successfully")
            logger.info(result.stdout)
            return True, result.stdout
        else:
            logger.error(f"Backup failed with code {result.returncode}")
            logger.error(result.stderr)
            return False, result.stderr
            
    except subprocess.TimeoutExpired:
        logger.error("Backup timed out after 10 minutes")
        return False, "Timeout"
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return False, str(e)


def update_status(success: bool, message: str):
    """Update the status file with last backup result."""
    status = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "message": message[:500],  # Truncate long messages
        "next_run": (datetime.now(timezone.utc).replace(
            hour=BACKUP_HOUR_UTC, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)).isoformat()
    }
    
    # Ensure directory exists
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)
    
    logger.info(f"Status updated: success={success}")


def get_seconds_until_next_run():
    """Calculate seconds until next backup time (3:00 AM UTC)."""
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=BACKUP_HOUR_UTC, minute=0, second=0, microsecond=0)
    
    # If we've passed today's backup time, schedule for tomorrow
    if now >= next_run:
        next_run += timedelta(days=1)
    
    delta = next_run - now
    return delta.total_seconds(), next_run


def main():
    """Main scheduler loop."""
    logger.info("=" * 50)
    logger.info("MongoDB Backup Scheduler Started")
    logger.info(f"Backup time: {BACKUP_HOUR_UTC}:00 UTC daily")
    logger.info("=" * 50)
    
    while True:
        try:
            seconds_to_wait, next_run = get_seconds_until_next_run()
            
            logger.info(f"Next backup scheduled: {next_run.isoformat()}")
            logger.info(f"Waiting {seconds_to_wait/3600:.1f} hours...")
            
            # Sleep until next backup time
            time.sleep(seconds_to_wait)
            
            # Run the backup
            success, message = run_backup()
            update_status(success, message)
            
            # Wait a minute before calculating next run
            # (to avoid running twice if there's clock drift)
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            # Wait 5 minutes before retrying on error
            time.sleep(300)


if __name__ == "__main__":
    main()
