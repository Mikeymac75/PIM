"""
Automatic database backups for PIM.

Runs a daemon thread that snapshots the SQLite database once per day using
sqlite3's online backup API (safe while the app is serving requests), then
prunes old snapshots.

Configuration (environment variables):
  PIM_BACKUP_DIR       Where snapshots go. In the Home Assistant add-on this
                       is /share/pim_backups, which an external backup system
                       (e.g. Proxmox Backup Server sweeping /share) will pick
                       up automatically. If unset or the parent doesn't exist,
                       backups are disabled with a log message.
  PIM_BACKUP_HOUR      Hour of day (0-23) to run. Default 2 (2 AM local) —
                       ahead of a typical 3 AM external backup window.
  PIM_BACKUP_KEEP      How many daily snapshots to keep. Default 7.
"""

import os
import sqlite3
import threading
import time
from datetime import datetime, date


def _log(msg):
    print(f"[pim-backup] {msg}", flush=True)


def _backup_once(db_path, backup_dir):
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    dest_path = os.path.join(backup_dir, f"food_app_{stamp}.db")
    src = sqlite3.connect(db_path)
    try:
        dest = sqlite3.connect(dest_path)
        try:
            with dest:
                src.backup(dest)
        finally:
            dest.close()
    finally:
        src.close()
    _log(f"Snapshot written: {dest_path}")
    return dest_path


def _prune(backup_dir, keep):
    try:
        snaps = sorted(
            f for f in os.listdir(backup_dir)
            if f.startswith("food_app_") and f.endswith(".db")
        )
    except FileNotFoundError:
        return
    excess = len(snaps) - keep
    for name in snaps[:max(0, excess)]:
        try:
            os.remove(os.path.join(backup_dir, name))
            _log(f"Pruned old snapshot: {name}")
        except OSError as e:
            _log(f"Could not prune {name}: {e}")


def _latest_snapshot_date(backup_dir):
    try:
        snaps = sorted(
            f for f in os.listdir(backup_dir)
            if f.startswith("food_app_") and f.endswith(".db")
        )
    except FileNotFoundError:
        return None
    if not snaps:
        return None
    # food_app_YYYY-MM-DD_HHMMSS.db
    try:
        return date.fromisoformat(snaps[-1][len("food_app_"):len("food_app_") + 10])
    except ValueError:
        return None


def _worker(db_path, backup_dir, hour, keep):
    # Catch-up snapshot on boot if we don't already have one from today.
    try:
        if _latest_snapshot_date(backup_dir) != date.today():
            _backup_once(db_path, backup_dir)
            _prune(backup_dir, keep)
    except Exception as e:
        _log(f"Startup backup failed: {e}")

    last_run_day = date.today()
    while True:
        time.sleep(300)  # check every 5 minutes
        now = datetime.now()
        if now.hour == hour and now.date() != last_run_day:
            try:
                _backup_once(db_path, backup_dir)
                _prune(backup_dir, keep)
                last_run_day = now.date()
            except Exception as e:
                _log(f"Scheduled backup failed: {e}")


def start_backup_scheduler(db_path):
    """Start the daily backup thread. No-op if PIM_BACKUP_DIR is unset/unusable."""
    backup_dir = os.environ.get("PIM_BACKUP_DIR", "").strip()
    if not backup_dir:
        _log("PIM_BACKUP_DIR not set — automatic backups disabled.")
        return None
    parent = os.path.dirname(backup_dir.rstrip("/")) or "/"
    if not os.path.isdir(parent):
        _log(f"Parent directory {parent} does not exist — automatic backups disabled.")
        return None
    try:
        hour = int(os.environ.get("PIM_BACKUP_HOUR", "2"))
    except ValueError:
        hour = 2
    hour = min(23, max(0, hour))
    try:
        keep = int(os.environ.get("PIM_BACKUP_KEEP", "7"))
    except ValueError:
        keep = 7
    keep = max(1, keep)

    t = threading.Thread(
        target=_worker, args=(db_path, backup_dir, hour, keep),
        name="pim-backup", daemon=True,
    )
    t.start()
    _log(f"Daily backups enabled: {backup_dir} at {hour:02d}:00, keeping {keep}.")
    return t
