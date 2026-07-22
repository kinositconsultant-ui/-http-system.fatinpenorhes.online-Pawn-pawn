"""Daily scheduled tasks for Fatin Penhores.

Each job records its outcome to the `job_runs` collection so the Dashboard
Scheduler card can display "last run" status (ok/failed + timestamp).
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path("/app/backups")
BACKUP_SCRIPT = "/app/scripts/build_backup.py"
RETENTION = 7  # keep last 7 daily snapshots

_scheduler: AsyncIOScheduler | None = None

JOB_IDS = ("daily_backup", "daily_reminders", "monthend_bundle", "alert_digest", "catalogue_refresh")


# ---------------------------------------------------------------------
# Job-run recording — one collection, one row per execution
# ---------------------------------------------------------------------
async def _record_job_run_async(
    job_id: str,
    status: str,
    duration_ms: int,
    details: dict | None = None,
) -> None:
    """Persist a single job execution outcome. Best-effort; never raises."""
    try:
        from deps import db  # local import to avoid heavy deps at module import
        await db.job_runs.insert_one({
            "job_id": job_id,
            "status": status,  # "ok" | "failed"
            "at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "details": details or {},
        })
    except Exception:
        logger.exception("[scheduler] could not record job run %s", job_id)


def _record_job_run_sync(job_id: str, status: str, duration_ms: int, details: dict | None = None) -> None:
    """Sync wrapper — opens its own event loop so plain sync jobs can call us."""
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_record_job_run_async(job_id, status, duration_ms, details))
        finally:
            loop.close()
    except Exception:
        logger.exception("[scheduler] record_job_run sync wrapper crashed")


async def _last_run(job_id: str) -> dict | None:
    """Return the most recent run doc for a job, or None."""
    try:
        from deps import db
        doc = await db.job_runs.find_one(
            {"job_id": job_id}, {"_id": 0},
            sort=[("at", -1)],
        )
        return doc
    except Exception:
        logger.exception("[scheduler] could not read last_run for %s", job_id)
        return None


def _stamp_from_name(name: str) -> str | None:
    m = re.search(r"(\d{8}-\d{4})", name)
    return m.group(1) if m else None


def run_backup_and_prune() -> None:
    """Synchronous job — run the backup script then prune old snapshots.
    Records outcome to job_runs on exit."""
    logger.info("[scheduler] daily backup starting")
    t0 = time.time()
    status = "ok"
    details: dict = {}
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
            status = "failed"
            details["error"] = proc.stderr[-500:]
        else:
            logger.info("[scheduler] backup script ok")
    except Exception as exc:
        logger.exception("[scheduler] backup script crashed")
        status = "failed"
        details["error"] = str(exc)
        _record_job_run_sync("daily_backup", status, int((time.time() - t0) * 1000), details)
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
    details["snapshots_kept"] = len(keep)
    details["files_pruned"] = removed
    _record_job_run_sync("daily_backup", status, int((time.time() - t0) * 1000), details)


def run_catalogue_refresh_sync() -> None:
    """Nightly rebuild of the public auction catalogue PDF cache.

    Runs at 01:00 UTC (10:00 Timor) so overnight status changes propagate to
    the public site before the day begins. Best-effort: on failure it logs
    and records the failure but never crashes the scheduler.
    """
    t0 = time.time()
    status = "ok"
    details: dict = {}
    try:
        # Import lazily so the scheduler module doesn't tug in server.py at load
        from server import get_or_build_catalogue_pdf, _CATALOGUE_CACHE  # noqa: PLC0415

        loop = asyncio.new_event_loop()
        try:
            pdf_bytes = loop.run_until_complete(get_or_build_catalogue_pdf(force=True))
        finally:
            loop.close()
        details["size_bytes"] = len(pdf_bytes)
        details["item_count"] = _CATALOGUE_CACHE.get("item_count", 0)
        details["next_auction_date"] = _CATALOGUE_CACHE.get("next_date", "")
        logger.info(
            "[catalogue] nightly refresh done — %d bytes, %d items, next auction %s",
            details["size_bytes"], details["item_count"], details["next_auction_date"] or "TBA",
        )
    except Exception as exc:
        logger.exception("[catalogue] nightly refresh failed")
        status = "failed"
        details["error"] = str(exc)
    _record_job_run_sync("catalogue_refresh", status, int((time.time() - t0) * 1000), details)


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
    # Month-end compliance bundle — 1st of every month at 02:30 UTC
    from routes.monthend import run_monthend_job_sync
    _scheduler.add_job(
        run_monthend_job_sync,
        CronTrigger(day=1, hour=2, minute=30),
        id="monthend_bundle",
        replace_existing=True,
        misfire_grace_time=3600 * 6,
    )
    # Pinned-view alert digest — daily at 23:00 UTC (~08:00 Timor next day)
    from routes.alerts import run_alert_digest_sync
    _scheduler.add_job(
        run_alert_digest_sync,
        CronTrigger(hour=23, minute=0),
        id="alert_digest",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Nightly auction-catalogue cache refresh — 01:00 UTC (10:00 Timor)
    _scheduler.add_job(
        run_catalogue_refresh_sync,
        CronTrigger(hour=1, minute=0),
        id="catalogue_refresh",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info("[scheduler] started — daily backup at 02:00 UTC, reminders at 00:00 UTC (09:00 Timor), month-end bundle at 02:30 UTC on day 1, alert digest at 23:00 UTC, keeping last %d snapshots", RETENTION)
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
    me_job = _scheduler.get_job("monthend_bundle")
    al_job = _scheduler.get_job("alert_digest")
    return {
        "running": True,
        "next_run_at": job.next_run_time.astimezone(timezone.utc).isoformat() if job and job.next_run_time else None,
        "next_reminders_run_at": rem_job.next_run_time.astimezone(timezone.utc).isoformat() if rem_job and rem_job.next_run_time else None,
        "next_monthend_run_at": me_job.next_run_time.astimezone(timezone.utc).isoformat() if me_job and me_job.next_run_time else None,
        "next_alert_digest_run_at": al_job.next_run_time.astimezone(timezone.utc).isoformat() if al_job and al_job.next_run_time else None,
        "retention": RETENTION,
        "now_utc": datetime.now(timezone.utc).isoformat(),
    }


async def next_run_info_with_last_runs() -> dict:
    """Same as next_run_info() plus a `last_runs` dict {job_id: {status, at, ...}}."""
    info = next_run_info()
    last_runs: dict[str, dict] = {}
    for jid in JOB_IDS:
        doc = await _last_run(jid)
        if doc:
            last_runs[jid] = doc
    info["last_runs"] = last_runs
    return info
