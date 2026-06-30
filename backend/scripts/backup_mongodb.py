#!/usr/bin/env python3
"""
MongoDB Backup Script for Humaniq Talent Vault
Performs daily backups of MongoDB Atlas database.

Usage:
    python backup_mongodb.py              # Run backup manually
    python backup_mongodb.py --restore    # List available backups
    python backup_mongodb.py --restore <backup_file>  # Restore from backup

Backups are stored in: /app/backups/
"""
import os
import sys
import json
import gzip
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

BACKUP_DIR = Path("/app/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Keep last 7 days of backups
MAX_BACKUPS = 7


def get_mongo_uri():
    """Get MongoDB connection URI from environment."""
    uri = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
    if not uri:
        print("ERROR: No database URI configured (ATLAS_URI or MONGO_URL)")
        sys.exit(1)
    return uri


def get_db_name():
    """Get database name from environment."""
    return os.environ.get('DB_NAME', 'atlas_talent_vault')


def create_backup():
    """Create a compressed backup of the MongoDB database."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    db_name = get_db_name()
    backup_file = BACKUP_DIR / f"backup_{db_name}_{timestamp}.archive.gz"
    
    print(f"Starting backup of database: {db_name}")
    print(f"Backup file: {backup_file}")
    
    mongo_uri = get_mongo_uri()
    
    # Use mongodump with gzip compression
    cmd = [
        "mongodump",
        f"--uri={mongo_uri}",
        f"--db={db_name}",
        f"--archive={backup_file}",
        "--gzip"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
            print(f"SUCCESS: Backup created - {file_size:.2f} MB")
            
            # Create metadata file
            metadata = {
                "timestamp": timestamp,
                "database": db_name,
                "file": str(backup_file),
                "size_mb": round(file_size, 2),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            metadata_file = backup_file.with_suffix('.json')
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Cleanup old backups
            cleanup_old_backups()
            
            return backup_file
        else:
            print(f"ERROR: Backup failed")
            print(f"STDERR: {result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("ERROR: Backup timed out after 10 minutes")
        return None
    except FileNotFoundError:
        print("ERROR: mongodump not found. Install MongoDB Database Tools.")
        print("Run: apt-get install -y mongodb-database-tools")
        return None


def cleanup_old_backups():
    """Remove backups older than MAX_BACKUPS days."""
    backups = sorted(BACKUP_DIR.glob("backup_*.archive.gz"), reverse=True)
    
    if len(backups) > MAX_BACKUPS:
        print(f"Cleaning up old backups (keeping last {MAX_BACKUPS})...")
        for old_backup in backups[MAX_BACKUPS:]:
            old_backup.unlink()
            # Remove metadata file too
            metadata_file = old_backup.with_suffix('.json')
            if metadata_file.exists():
                metadata_file.unlink()
            print(f"  Removed: {old_backup.name}")


def list_backups():
    """List all available backups."""
    backups = sorted(BACKUP_DIR.glob("backup_*.archive.gz"), reverse=True)
    
    if not backups:
        print("No backups found.")
        return
    
    print(f"\nAvailable backups ({len(backups)} total):")
    print("-" * 60)
    
    for backup in backups:
        size_mb = backup.stat().st_size / (1024 * 1024)
        
        # Try to read metadata
        metadata_file = backup.with_suffix('.json')
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                created = metadata.get('created_at', 'Unknown')[:19]
        else:
            created = "Unknown"
        
        print(f"  {backup.name}")
        print(f"    Size: {size_mb:.2f} MB | Created: {created}")
    
    print("-" * 60)
    print(f"\nTo restore: python backup_mongodb.py --restore <filename>")


def restore_backup(backup_file: str):
    """Restore database from a backup file."""
    backup_path = BACKUP_DIR / backup_file
    
    if not backup_path.exists():
        print(f"ERROR: Backup file not found: {backup_path}")
        list_backups()
        return False
    
    mongo_uri = get_mongo_uri()
    db_name = get_db_name()
    
    print(f"WARNING: This will REPLACE all data in database '{db_name}'!")
    print(f"Backup file: {backup_file}")
    
    confirm = input("Type 'RESTORE' to confirm: ")
    if confirm != "RESTORE":
        print("Restore cancelled.")
        return False
    
    print(f"Restoring from: {backup_path}")
    
    cmd = [
        "mongorestore",
        f"--uri={mongo_uri}",
        f"--archive={backup_path}",
        "--gzip",
        "--drop"  # Drop existing collections before restore
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            print("SUCCESS: Database restored successfully!")
            return True
        else:
            print(f"ERROR: Restore failed")
            print(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("ERROR: Restore timed out after 10 minutes")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--restore":
            if len(sys.argv) > 2:
                restore_backup(sys.argv[2])
            else:
                list_backups()
        elif sys.argv[1] == "--list":
            list_backups()
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print(__doc__)
    else:
        create_backup()


if __name__ == "__main__":
    main()
