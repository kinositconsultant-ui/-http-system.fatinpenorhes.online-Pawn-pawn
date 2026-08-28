#!/usr/bin/env python3
"""Restore the Fatin Penhores MongoDB database from a backup zip.

Usage: python restore_backup.py /app/backups/mongodb-backup-XXXX.zip

Steps:
  1. Safety snapshot of the CURRENT database → /app/backups/pre-restore-<stamp>.zip
  2. Extract the given zip, locate the mongodump db folder inside
  3. mongorestore --drop into the current DB (full replace)

Prints a single JSON line with the result on the last stdout line.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/app/backups")
ROOT.mkdir(exist_ok=True)
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _env(key: str) -> str:
    v = os.environ.get(key)
    if v:
        return v.strip().strip('"').strip("'")
    for line in open("/app/backend/.env"):
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise KeyError(key)


MONGO_URL = _env("MONGO_URL")
DB_NAME = _env("DB_NAME")


def fail(msg: str) -> None:
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: restore_backup.py <zip_path>")
    zip_path = Path(sys.argv[1])
    if not zip_path.is_file():
        fail(f"backup file not found: {zip_path}")

    # ---- 1. Safety snapshot of current data --------------------------------
    safety_dir = ROOT / f"mongodump-pre-{STAMP}"
    r = subprocess.run(
        ["mongodump", f"--uri={MONGO_URL}", f"--db={DB_NAME}", f"--out={safety_dir}", "--quiet"],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        fail(f"safety mongodump failed: {r.stderr[-500:]}")
    safety_zip = ROOT / f"pre-restore-{STAMP}.zip"
    with zipfile.ZipFile(safety_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in safety_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(safety_dir.parent))
    shutil.rmtree(safety_dir)
    # Keep only the 3 most recent pre-restore snapshots
    pre = sorted(ROOT.glob("pre-restore-*.zip"))
    for old in pre[:-3]:
        old.unlink(missing_ok=True)

    # ---- 2. Extract the backup zip ------------------------------------------
    tmp = Path(tempfile.mkdtemp(prefix="restore-"))
    try:
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp)
        bson_files = list(tmp.rglob("*.bson"))
        if not bson_files:
            fail("zip does not contain a mongodump (.bson files not found)")
        db_dir = bson_files[0].parent
        src_db = db_dir.name
        n_colls = len([b for b in db_dir.glob("*.bson")])

        # ---- 3. Full-replace restore ----------------------------------------
        cmd = [
            "mongorestore", f"--uri={MONGO_URL}", "--drop", "--quiet",
            f"--nsInclude={src_db}.*",
            f"--nsFrom={src_db}.*", f"--nsTo={DB_NAME}.*",
            str(db_dir.parent),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if r.returncode != 0:
            fail(f"mongorestore failed: {r.stderr[-800:]}")

        print(json.dumps({
            "ok": True,
            "restored_from": zip_path.name,
            "source_db": src_db,
            "collections": n_colls,
            "safety_backup": safety_zip.name,
        }))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
