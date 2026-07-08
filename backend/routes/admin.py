"""Admin router — backup downloads + audit log listing + health.

Extracted from server.py during Phase 2 refactor.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from deps import db, require_admin, write_audit

router = APIRouter()

@router.get("/admin/backups")
async def list_backups(_: dict = Depends(require_admin)):
    """List all backup artifacts in /app/backups/."""
    import os
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
    import subprocess
    import sys
    import os
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
    import subprocess
    import sys
    import os
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
    import os
    import re
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
