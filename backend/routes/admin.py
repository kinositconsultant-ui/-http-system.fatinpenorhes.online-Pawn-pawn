"""Admin router — backup downloads + audit log listing + health.

Extracted from server.py during Phase 2 refactor.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from deps import db, get_current_user, require_admin, utcnow_iso, write_audit
from realtime import notify as rt_notify

router = APIRouter()

@router.get("/admin/backups")
async def list_backups(_: dict = Depends(require_admin)):
    """List all backup artifacts in /app/backups/."""
    folder = "/app/backups"
    if not os.path.isdir(folder):
        return []
    items = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if os.path.isfile(p):
            items.append({
                "name": name,
                "size": os.path.getsize(p),
                "modified": datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc).isoformat(),
            })
    return items


@router.post("/admin/backups/generate")
async def generate_backup(admin: dict = Depends(require_admin)):
    """Run the backup script and return the resulting file list."""
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "/app/scripts/build_backup.py"],
        capture_output=True, text=True, env=env, cwd="/app", timeout=300,
    )
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail={"stderr": proc.stderr[-2000:], "stdout": proc.stdout[-2000:]})
    await write_audit(admin, "backup", "system", "all", {"stdout_tail": proc.stdout[-500:]})
    return await list_backups(_=admin)  # type: ignore[arg-type]


@router.post("/admin/backups/generate-project")
async def generate_project_backup(admin: dict = Depends(require_admin)):
    """Build the complete deployment zip (backend + frontend + Mongo + docs)."""
    env = os.environ.copy()
    proc = subprocess.run(
        [sys.executable, "/app/scripts/build_full_project_backup.py"],
        capture_output=True, text=True, env=env, cwd="/app", timeout=300,
    )
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail={"stderr": proc.stderr[-2000:], "stdout": proc.stdout[-2000:]})
    await write_audit(admin, "backup_project", "system", "all", {"stdout_tail": proc.stdout[-500:]})
    return await list_backups(_=admin)  # type: ignore[arg-type]


@router.get("/admin/backups/schedule")
async def backup_schedule(_: dict = Depends(require_admin)):
    """Return APScheduler status + last-run outcome for each scheduled job."""
    try:
        from scheduler import next_run_info_with_last_runs
        return await next_run_info_with_last_runs()
    except Exception as e:  # noqa: BLE001
        return {"running": False, "error": str(e)}


@router.get("/admin/backups/{name}")
async def download_backup(name: str, _: dict = Depends(require_admin)):
    """Stream a backup artifact for download. Admin-only."""
    if not re.match(r"^[\w.\-]+$", name):
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join("/app/backups", name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Not found")
    media = "application/zip" if name.endswith(".zip") else "text/plain; charset=utf-8"
    def _iter():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
    return StreamingResponse(
        _iter(),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# =====================================================================
# System Restore (admin-only, full replace)
# =====================================================================
RESTORABLE_PREFIXES = ("mongodb-backup-", "pre-restore-", "uploaded-restore-")


def _zip_has_mongodump(path: str) -> bool:
    try:
        with zipfile.ZipFile(path) as zf:
            return any(n.endswith(".bson") for n in zf.namelist())
    except zipfile.BadZipFile:
        return False


async def _run_restore(zip_path: str, admin: dict, display_name: str | None = None) -> dict:
    if not _zip_has_mongodump(zip_path):
        raise HTTPException(status_code=400, detail="Not a valid database backup zip (no mongodump .bson files inside)")
    proc = subprocess.run(
        [sys.executable, "/app/scripts/restore_backup.py", zip_path],
        capture_output=True, text=True, cwd="/app", timeout=600, check=False,
    )
    result = {}
    for line in reversed((proc.stdout or "").strip().splitlines()):
        try:
            result = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if proc.returncode != 0 or not result.get("ok"):
        detail = result.get("error") or proc.stderr[-800:] or "Restore failed"
        raise HTTPException(status_code=500, detail=detail)
    if display_name:
        result["restored_from"] = display_name
    await write_audit(admin, "restore", "system", "all", {
        "restored_from": result.get("restored_from"),
        "collections": result.get("collections"),
        "safety_backup": result.get("safety_backup"),
    })
    # Post-restore marker (written into the freshly-restored DB) + live push so
    # every signed-in staff member sees the "data changed" banner.
    now = utcnow_iso()
    await db.system_status.update_one(
        {"id": "singleton"},
        {"$set": {
            "id": "singleton",
            "last_restore_at": now,
            "restored_from": result.get("restored_from"),
            "restored_by": admin.get("email"),
        }},
        upsert=True,
    )
    rt_notify("system.restored", {
        "restored_from": result.get("restored_from"),
        "restored_by": admin.get("email"),
        "at": now,
    })
    return result


@router.get("/system/status")
async def system_status(_: dict = Depends(get_current_user)):
    """Lightweight status poll — lets every page detect a recent restore."""
    doc = await db.system_status.find_one({"id": "singleton"}, {"_id": 0}) or {}
    return {
        "last_restore_at": doc.get("last_restore_at"),
        "restored_from": doc.get("restored_from"),
        "restored_by": doc.get("restored_by"),
    }


@router.post("/admin/restore/upload")
async def restore_from_upload(file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    """Upload a backup zip and restore it (full replace of current data).

    The zip is written to a transient temp file only for the duration of the
    mongorestore run, then deleted — nothing is persisted on the pod.
    """
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip backup file")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Backup file too large (200MB max)")
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        return await _run_restore(tmp.name, admin, display_name=file.filename)
    finally:
        os.unlink(tmp.name)


@router.post("/admin/restore/{name}")
async def restore_from_backup(name: str, admin: dict = Depends(require_admin)):
    """Restore the database from an existing backup snapshot (full replace)."""
    if not re.match(r"^[\w.\-]+$", name) or not name.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not name.startswith(RESTORABLE_PREFIXES):
        raise HTTPException(status_code=400, detail="Only database backup zips can be restored")
    path = os.path.join("/app/backups", name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Backup not found")
    return await _run_restore(path, admin)


# =====================================================================
# Audit log — list + filters (date range, actor, resource, action) + CSV + PDF
# =====================================================================
@router.get("/audit-log")
async def audit_log_list(
    limit: int = Query(200, ge=1, le=2000),
    resource: Optional[str] = None,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    _: dict = Depends(require_admin),
):
    q: dict = {}
    if resource:
        q["resource"] = resource
    if action:
        q["action"] = action
    if actor_email:
        q["actor_email"] = {"$regex": re.escape(actor_email), "$options": "i"}
    if date_from or date_to:
        rng: dict = {}
        if date_from:
            rng["$gte"] = f"{date_from}T00:00:00"
        if date_to:
            rng["$lte"] = f"{date_to}T23:59:59"
        q["created_at"] = rng
    rows = await db.audit_log.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return rows


@router.get("/audit-log/export/csv")
async def audit_log_export_csv(
    limit: int = Query(1000, ge=1, le=5000),
    resource: Optional[str] = None,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    """CSV export of the (filtered) audit log."""
    import csv
    import io
    rows = await audit_log_list(  # type: ignore[misc]
        limit=limit, resource=resource, action=action,
        actor_email=actor_email, date_from=date_from, date_to=date_to, _=_,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["created_at", "actor_email", "actor_id", "action",
                     "resource", "resource_id", "details"])
    for r in rows:
        writer.writerow([
            r.get("created_at", ""),
            r.get("actor_email", ""),
            r.get("actor_id", ""),
            r.get("action", ""),
            r.get("resource", ""),
            r.get("resource_id", ""),
            (r.get("details") or ""),
        ])
    from fastapi import Response
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit-log-{datetime.now(timezone.utc).date().isoformat()}.csv"'},
    )


@router.get("/audit-log/export/pdf")
async def audit_log_export_pdf(
    limit: int = Query(500, ge=1, le=2000),
    resource: Optional[str] = None,
    action: Optional[str] = None,
    actor_email: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    _: dict = Depends(require_admin),
):
    """Branded PDF export of the (filtered) audit log."""
    from pdf_utils import build_audit_log_pdf
    rows = await audit_log_list(  # type: ignore[misc]
        limit=limit, resource=resource, action=action,
        actor_email=actor_email, date_from=date_from, date_to=date_to, _=_,
    )
    pdf_bytes = build_audit_log_pdf(rows, filters={
        "resource": resource, "action": action,
        "actor_email": actor_email, "date_from": date_from, "date_to": date_to,
    })
    from fastapi import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="audit-log-{datetime.now(timezone.utc).date().isoformat()}.pdf"'},
    )


# =====================================================================
# Health
# =====================================================================
@router.get("/")
async def root():
    return {"service": "Fatin Penhores Pawn System", "status": "ok"}
