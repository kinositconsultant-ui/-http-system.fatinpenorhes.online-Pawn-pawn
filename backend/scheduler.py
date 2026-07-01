"""Daily scheduled tasks for Fatin Penhores.

Currently:
- 02:00 UTC daily: run the migration backup script and prune anything older
  than 7 days from /app/backups/ (keeping the latest 7 snapshots only).
"""
from __future__ import annotations

import os
import re
import shutil
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path("/app/backups")
BACKUP_SCRIPT = "/app/scripts/build_backup.py"
RETENTION = 7  # keep last 7 daily snapshots

_scheduler: AsyncIOScheduler | None = None


def _stamp_from_name(name: str) -> str | None:
    m = re.search(r"(\d{8}-\d{4})", name)
    return m.group(1) if m else None


def run_backup_and_prune() -> None:
    """Synchronous job — run the backup script then prune old snapshots."""
    logger.info("[scheduler] daily backup starting")
    try:
        env = os.environ.copy()
        proc = subprocess.run(
            ["python3", BACKUP_SCRIPT],
            cwd="/app",
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode != 0:
            logger.error("[scheduler] backup script failed: %s", proc.stderr[-1000:])
            return
        logger.info("[scheduler] backup script ok")
    except Exception:
        logger.exception("[scheduler] backup script crashed")
        return

    # Group all generated files by their <stamp> suffix and keep the last RETENTION groups
    BACKUP_ROOT.mkdir(exist_ok=True)
    stamps: dict[str, list[Path]] = {}
    for f in BACKUP_ROOT.iterdir():
        if not f.is_file():
            continue
        s = _stamp_from_name(f.name)
        if s:
            stamps.setdefault(s, []).append(f)
    # Sort stamps descending (newest first)
    ordered = sorted(stamps.keys(), reverse=True)
    keep = set(ordered[:RETENTION])
    removed = 0
    for stamp, files in stamps.items():
        if stamp in keep:
            continue
        for f in files:
            try:
                f.unlink()
                removed += 1
            except Exception:
                logger.exception("[scheduler] could not remove %s", f)
    if removed:
        logger.info("[scheduler] pruned %d old backup files (kept last %d snapshots)", removed, RETENTION)


def start_scheduler() -> AsyncIOScheduler:
    """Start the APScheduler with the daily jobs. Idempotent."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        run_backup_and_prune,
        CronTrigger(hour=2, minute=0),
        id="daily_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Daily WhatsApp overdue reminders — 09:00 Timor (UTC+9) → 00:00 UTC
    from reminders import run_daily_reminders_sync
    _scheduler.add_job(
        run_daily_reminders_sync,
        CronTrigger(hour=0, minute=0),
        id="daily_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("[scheduler] started — daily backup at 02:00 UTC, reminders at 00:00 UTC (09:00 Timor), keeping last %d snapshots", RETENTION)
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def next_run_info() -> dict:
    """Return scheduler status for the admin UI."""
    if _scheduler is None:
        return {"running": False, "next_run_at": None, "retention": RETENTION}
    job = _scheduler.get_job("daily_backup")
    rem_job = _scheduler.get_job("daily_reminders")
    return {
        "running": True,
        "next_run_at": job.next_run_time.astimezone(timezone.utc).isoformat() if job and job.next_run_time else None,
        "next_reminders_run_at": rem_job.next_run_time.astimezone(timezone.utc).isoformat() if rem_job and rem_job.next_run_time else None,
        "retention": RETENTION,
        "now_utc": datetime.now(timezone.utc).isoformat(),
    }
