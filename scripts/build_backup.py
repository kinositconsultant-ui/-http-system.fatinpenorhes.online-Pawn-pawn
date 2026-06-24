#!/usr/bin/env python3
"""Build a complete migration backup for Fatin Penhores Pawn System.

Outputs in /app/backups/:
  - mongodb-backup-<YYYYMMDD-HHMM>.zip      (mongodump archive of all collections)
  - uploads-backup-<YYYYMMDD-HHMM>.zip      (every photo & document from object storage)
  - env-template.txt                        (structure of .env with NO real secrets)
  - collections.txt                         (list of all collections + document counts)
  - README.md                               (instructions to restore on your server)
"""
from __future__ import annotations

import os
import sys
import json
import shutil
import zipfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app/backend")

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path("/app/backups")
ROOT.mkdir(exist_ok=True)
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")

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


# ---------- 1. MongoDB dump ------------------------------------------------
print(f"\n=== [1/4] Dumping MongoDB database '{DB_NAME}' ===")
dump_dir = ROOT / f"mongodump-{STAMP}"
if dump_dir.exists():
    shutil.rmtree(dump_dir)
result = subprocess.run(
    ["mongodump", f"--uri={MONGO_URL}", f"--db={DB_NAME}", f"--out={dump_dir}", "--quiet"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    print("mongodump failed:", result.stderr)
    sys.exit(1)

mongo_zip = ROOT / f"mongodb-backup-{STAMP}.zip"
with zipfile.ZipFile(mongo_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in dump_dir.rglob("*"):
        if f.is_file():
            zf.write(f, f.relative_to(dump_dir.parent))
shutil.rmtree(dump_dir)
print(f"  ✅ {mongo_zip.name}  ({mongo_zip.stat().st_size / 1024:.1f} KB)")


# ---------- 2. List collections -------------------------------------------
async def list_colls():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    out = []
    for name in await db.list_collection_names():
        cnt = await db[name].count_documents({})
        out.append((name, cnt))
    client.close()
    return sorted(out)

print("\n=== [2/4] Listing collections ===")
colls = asyncio.run(list_colls())
collections_txt = ROOT / "collections.txt"
with collections_txt.open("w") as f:
    f.write(f"# Collections in {DB_NAME}  (snapshot: {STAMP} UTC)\n")
    f.write(f"# Total: {len(colls)} collections, {sum(c for _, c in colls)} documents\n\n")
    for name, cnt in colls:
        f.write(f"{name:<30s} {cnt:>8d} documents\n")
        print(f"  • {name:<30s} {cnt:>6d} docs")
print(f"  ✅ {collections_txt.name}")


# ---------- 3. Uploaded files archive (object storage) --------------------
print("\n=== [3/4] Downloading all uploaded files from object storage ===")

async def collect_file_refs():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    refs: list[tuple[str, str]] = []   # (object_path, source_label)

    async def collect(coll_name, fields):
        async for doc in db[coll_name].find({}, {"_id": 0}):
            for f in fields:
                v = doc.get(f)
                if v and isinstance(v, str) and not v.startswith("http"):
                    label = f"{coll_name}/{doc.get('id', '_')}/{f}"
                    refs.append((v, label))

    await collect("clients", ["photo_url", "document_url"])
    for coll in ["cars", "motorcycles", "electronics", "pezadus"]:
        await collect(coll, ["photo_url", "document_url"])
    # Also harvest every entry in the 'files' upload registry, even if not linked yet
    async for f in db.files.find({"is_deleted": {"$ne": True}}, {"_id": 0}):
        for k in ("storage_path", "path", "object_path", "url", "key"):
            v = f.get(k)
            if v and isinstance(v, str) and not v.startswith("http"):
                refs.append((v, f"files/{f.get('id', '_')}/{k}"))
                break
    client.close()
    return refs

refs = asyncio.run(collect_file_refs())
print(f"  Found {len(refs)} file references in DB.")

from storage import get_object  # type: ignore  # noqa
files_zip = ROOT / f"uploads-backup-{STAMP}.zip"
ok = fail = 0
with zipfile.ZipFile(files_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    seen = set()
    for path, label in refs:
        if path in seen:
            continue
        seen.add(path)
        try:
            blob, ctype = get_object(path)
            # preserve original path inside zip
            arcname = f"uploads/{path}"
            zf.writestr(arcname, blob)
            # index entry
            ok += 1
        except Exception as e:
            fail += 1
            print(f"    ! could not fetch {path}: {e}")
    # also add an index manifest
    manifest = {
        "stamp_utc": STAMP,
        "total_refs": len(refs),
        "downloaded": ok,
        "failed": fail,
        "refs": [{"object_path": p, "source": l} for p, l in refs],
    }
    zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))
print(f"  ✅ {files_zip.name}  ({files_zip.stat().st_size / 1024:.1f} KB) — downloaded {ok}, failed {fail}")


# ---------- 4. .env template (sanitized) ----------------------------------
print("\n=== [4/4] Building .env template ===")
env_lines = []
with open("/app/backend/.env") as f:
    for line in f:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            env_lines.append(line.rstrip())
            continue
        k = s.split("=", 1)[0]
        # Sensitive keys -> redact value
        sensitive = {
            "MONGO_URL": "mongodb://localhost:27017",
            "DB_NAME": "fatin_penhores",
            "JWT_SECRET": "<COPY-FROM-EMERGENT-OR-GENERATE-NEW>",
            "WHATSAPP_ENCRYPTION_KEY": "<COPY-FROM-EMERGENT-OR-LOSE-SAVED-TOKEN>",
            "ADMIN_EMAIL": "admin@fatinpenhores.tl",
            "ADMIN_PASSWORD": "<set-your-admin-password>",
            "EMERGENT_LLM_KEY": "<NOT-NEEDED-IF-NOT-USING-LLM>  # or your own OpenAI key",
            "WHATSAPP_API_VERSION": "v22.0",
        }
        env_lines.append(f"{k}={sensitive.get(k, '<copy from Emergent .env>')}")

env_template = ROOT / "env-template.txt"
with env_template.open("w") as f:
    f.write("# .env template for Fatin Penhores production deployment\n")
    f.write(f"# Generated: {STAMP} UTC\n")
    f.write("# Replace each placeholder with the matching value from /app/backend/.env on Emergent.\n")
    f.write("# CRITICAL: keep WHATSAPP_ENCRYPTION_KEY identical, or you lose access to the saved WhatsApp token.\n\n")
    f.write("\n".join(env_lines))
    f.write("\n")
print(f"  ✅ {env_template.name}")


# ---------- 5. README ----------------------------------------------------
print("\n=== Writing README.md ===")
readme = ROOT / "README.md"
readme.write_text(f"""# Fatin Penhores — Migration Backup

Snapshot taken: **{STAMP} UTC**

## Files in this folder

| File | Purpose |
|---|---|
| `mongodb-backup-{STAMP}.zip` | Full `mongodump` of the `{DB_NAME}` database |
| `uploads-backup-{STAMP}.zip` | All client documents & item photos (with `MANIFEST.json`) |
| `env-template.txt` | Structure of the production `.env` — fill in secrets before use |
| `collections.txt` | Counts of every collection at backup time |

## Restore on your own server

```bash
# 1. MongoDB
unzip mongodb-backup-{STAMP}.zip -d ./
mongorestore --uri="mongodb://localhost:27017" --db={DB_NAME} ./mongodump-{STAMP}/{DB_NAME}

# 2. Verify
mongosh
> use {DB_NAME}
> db.clients.countDocuments()      # should match the number in collections.txt
> db.contracts.countDocuments()    # ditto
```

## Restore uploaded files
The zip contains files under `uploads/<object-path>`. After unzipping, your
storage backend (S3, local disk, etc.) should serve them under the same paths
referenced by `photo_url` / `document_url` columns in the DB.

## SECURE THESE FILES
The MongoDB dump contains every client's personal data (BI/passport numbers,
phone, address). Treat the zip files as **confidential** — keep them in an
encrypted folder, never commit to GitHub, and limit who can access them.
""")
print(f"  ✅ {readme.name}\n")

print("=== DONE ===")
print(f"All files in: {ROOT}")
