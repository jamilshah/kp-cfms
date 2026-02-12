# Data Backup & Restore Guide

## Overview
This system provides two Django management commands for safe data export/import that properly handle relationships and sequences.

## Why This Approach?
- ✓ Handles foreign key relationships automatically
- ✓ Preserves sequence IDs (auto-increment counters)
- ✓ Excludes Django system tables (migrations, content_types)
- ✓ Can disable constraints during import to handle any data order
- ✓ Human-readable JSON format

## Quick Start

### On Windows (Source Machine)

**1. Export data:**
```bash
cd D:\apps\jango\cfms
python manage.py export_data --output backup.json
```

Output: `backup.json` file containing all application data

**2. Transfer file to server**
```bash
# Using SCP or your preferred method
scp backup.json misapp@175.107.59.132:/home/misapp/kp-cfms/
```

### On Ubuntu Server (Target Machine)

**1. Stop the running application**
```bash
# If using gunicorn
sudo systemctl stop kp-cfms

# Or stop the development server with Ctrl+C
```

**2. Delete old data (optional but recommended)**
```bash
# Connect to database
psql -h localhost -U jamil -d cfm

# Drop the database
DROP DATABASE cfm;

# Create fresh empty database
CREATE DATABASE cfm OWNER jamil;

# Exit psql
\q
```

**3. Apply migrations to create tables**
```bash
cd /home/misapp/kp-cfms
source venv/bin/activate
python manage.py migrate
```

**4. Import data from backup**
```bash
python manage.py import_data backup.json --disable-constraints
```

The `--disable-constraints` flag temporarily disables foreign key checks during import, preventing issues with data order.

**5. Restart application**
```bash
# Start development server
python manage.py runserver 0.0.0.0:8000

# Or restart gunicorn service
sudo systemctl start kp-cfms
```

---

## Command Reference

### export_data

**Usage:**
```bash
python manage.py export_data [OPTIONS]
```

**Options:**
- `--output FILE` - Output file path (default: `data_backup.json`)
- `--exclude-django` - Exclude Django system tables

**Examples:**
```bash
# Export with default name
python manage.py export_data

# Export to custom location
python manage.py export_data --output /backups/cfms_2026_02_11.json

# Export without Django tables
python manage.py export_data --exclude-django
```

**What gets exported:**
- ✓ core (Organizations, Districts, Divisions, etc.)
- ✓ users (All users and roles)
- ✓ finance (Budget heads, vouchers, charts of accounts)
- ✓ budgeting (Budget allocations, fiscal years, employees)
- ✓ expenditure (Bills, payments, tax configurations)
- ✓ revenue (Revenue demands, collections)
- ✓ property (Properties, leases, mauzas)
- ✓ reporting (Reports configuration)
- ✓ dashboard (Configured dashboards)
- ✓ system_admin (System settings)

### import_data

**Usage:**
```bash
python manage.py import_data FIXTURE_FILE [OPTIONS]
```

**Arguments:**
- `FIXTURE_FILE` - Path to JSON fixture file (required)

**Options:**
- `--noinput` - Skip confirmation prompt
- `--disable-constraints` - Disable FK constraints during import (recommended)

**Examples:**
```bash
# Interactive import with confirmation
python manage.py import_data backup.json

# Import without prompting
python manage.py import_data backup.json --noinput

# Import with constraints disabled (safe for complex data)
python manage.py import_data backup.json --disable-constraints

# Non-interactive with constraints disabled
python manage.py import_data backup.json --noinput --disable-constraints
```

---

## Troubleshooting

### File too large to transfer
If the JSON file is too large:

```bash
# On Windows - compress before sending
gzip backup.json

# On server - decompress
gunzip backup.json.gz
python manage.py import_data backup.json
```

### Import fails with foreign key errors
Use `--disable-constraints`:
```bash
python manage.py import_data backup.json --disable-constraints
```

### Import fails midway
Database is in an inconsistent state. Recovery:

```bash
# Drop and recreate database
psql -h localhost -U jamil -d postgres << EOF
DROP DATABASE cfm WITH (FORCE);
CREATE DATABASE cfm OWNER jamil;
EOF

# Reapply migrations
python manage.py migrate

# Try import again with constraints disabled
python manage.py import_data backup.json --disable-constraints
```

### Data looks incomplete
Check import output for errors:
```bash
# Re-import with verbose output
python manage.py import_data backup.json --disable-constraints 2>&1 | tee import.log
```

Examine `import.log` for error messages.

---

## Advanced Usage

### Export specific data for testing
Edit `apps/core/management/commands/export_data.py` to customize which apps are exported.

### Schedule regular backups (Linux cron)
```bash
# Add to crontab: crontab -e
0 2 * * * cd /home/misapp/kp-cfms && python manage.py export_data --output /backups/cfms_$(date +\%Y_\%m_\%d).json
```

### Backup compressed to cloud
```bash
# After export
gzip backup.json
# Then upload with scp, aws s3, etc.
```

---

## Performance Notes

- **Export time**: ~30 seconds - 5 minutes (depending on data volume)
- **Import time**: ~1-10 minutes (depending on constraints settings)
- **File size**: Typically 10-200 MB for a full system

Large imports are slower with `--disable-constraints` enabled, but more reliable.

---

## Security Considerations

- ⚠ Fixture files contain sensitive data (passwords hashed, but still contains all business data)
- ✓ Store backups securely
- ✓ Use SSH/encrypted transfer channels
- ✓ Follow your organization's backup policies

---

## Automated Full Workflow Script

Save this as `backup_and_restore.sh` for one-command backup+transfer:

```bash
#!/bin/bash
set -e

# Configuration
WINDOWS_KP_CFMS="/d/apps/jango/cfms"  # Adjust to your path
SERVER_USER="misapp"
SERVER_IP="175.107.59.132"
SERVER_PATH="/home/misapp/kp-cfms"
BACKUP_FILE="cfms_backup_$(date +%Y_%m_%d_%H%M%S).json"

echo "=== KP-CFMS Backup & Transfer ==="

# Windows: Export data
echo "1. Exporting data from Windows..."
cd "$WINDOWS_KP_CFMS"
python manage.py export_data --output "$BACKUP_FILE"

# Transfer to server
echo "2. Transferring to server..."
scp "$BACKUP_FILE" "$SERVER_USER@$SERVER_IP:$SERVER_PATH/"

echo "3. Import on server (manual step - SSH and run):"
echo "   ssh misapp@175.107.59.132"
echo "   cd /home/misapp/kp-cfms"
echo "   python manage.py import_data $BACKUP_FILE --disable-constraints"

echo "✓ Backup complete: $BACKUP_FILE"
```

Usage:
```bash
bash backup_and_restore.sh
```

---

Last updated: February 11, 2026
