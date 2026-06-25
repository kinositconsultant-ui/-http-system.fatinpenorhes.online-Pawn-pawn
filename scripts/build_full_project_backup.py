#!/usr/bin/env python3
"""Build the complete deployment backup zip for Fatin Penhores Pawn System.

Output: /app/backups/FatinPenhores_Full_Project_Backup.zip

Contents:
  backend/           — all Python source, requirements, .env.template, assets
  frontend/          — entire src/, public/, package.json, package-lock.json, craco.config.js, tailwind.config.js, .env.template
  mongodb_backup/    — mongodump archive + restore instructions
  scripts/           — build_backup.py (this tool)
  README.md          — top-level deployment guide
  DEPLOYMENT.md      — full deployment guide
  collections.txt    — snapshot of all collections + counts
  .gitignore         — production-safe ignore rules
"""
from __future__ import annotations

import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app/backend")
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path("/app")
OUT_DIR = Path("/app/backups")
OUT_DIR.mkdir(exist_ok=True)
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
STAGE = OUT_DIR / f"FatinPenhores_Project_{STAMP}"
ZIP_PATH = OUT_DIR / "FatinPenhores_Full_Project_Backup.zip"

if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir(parents=True)


def _env(key: str) -> str:
    for line in open("/app/backend/.env"):
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


MONGO_URL = _env("MONGO_URL")
DB_NAME = _env("DB_NAME")


# ============================================================
# 1. Backend
# ============================================================
print("[1/6] Copying backend source...")
backend_dest = STAGE / "backend"
backend_dest.mkdir()
backend_files = [
    "server.py", "auth.py", "encryption.py", "storage.py",
    "scheduler.py", "whatsapp.py", "pdf_utils.py",
    "requirements.txt",
]
for f in backend_files:
    src = ROOT / "backend" / f
    if src.exists():
        shutil.copy2(src, backend_dest / f)
# assets folder
src_assets = ROOT / "backend" / "assets"
if src_assets.exists():
    shutil.copytree(src_assets, backend_dest / "assets")
# tests
src_tests = ROOT / "backend" / "tests"
if src_tests.exists():
    shutil.copytree(src_tests, backend_dest / "tests")

# Backend .env template (no secrets)
(backend_dest / ".env.template").write_text("""# === Database ===
MONGO_URL=mongodb://127.0.0.1:27017
DB_NAME=pawn

# === App ===
APP_NAME=fatin-penhores

# === CORS — list exact origins; never use '*' when using cookies ===
CORS_ORIGINS=https://fatinpenorhes.online,https://www.fatinpenorhes.online

# === Authentication ===
JWT_SECRET=GENERATE_WITH_openssl_rand_hex_32
ADMIN_EMAIL=admin@fatinpenhores.tl
ADMIN_PASSWORD=ChangeMeNow!

# === WhatsApp token encryption ===
# CRITICAL: copy the EXACT value from Emergent if you migrated,
# otherwise the saved WhatsApp token will be unreadable and must be
# re-entered in Settings.
WHATSAPP_ENCRYPTION_KEY=GENERATE_WITH_python_-c_from-cryptography.fernet-import-Fernet-print-Fernet.generate_key-decode
WHATSAPP_API_VERSION=v22.0

# === Optional ===
# WHATSAPP_TOKEN=        # only if you prefer env over Settings UI
# WHATSAPP_PHONE_ID=
# EMERGENT_LLM_KEY=      # ONLY works on Emergent platform; remove on self-host
""")
print("    backend/ done")


# ============================================================
# 2. Frontend
# ============================================================
print("[2/6] Copying frontend source...")
frontend_dest = STAGE / "frontend"
frontend_dest.mkdir()
frontend_src = ROOT / "frontend"
for item in ["src", "public"]:
    if (frontend_src / item).exists():
        shutil.copytree(frontend_src / item, frontend_dest / item)
for f in ["package.json", "package-lock.json", "yarn.lock",
          "craco.config.js", "tailwind.config.js", "postcss.config.js",
          "jsconfig.json", "components.json"]:
    if (frontend_src / f).exists():
        shutil.copy2(frontend_src / f, frontend_dest / f)

(frontend_dest / ".env.template").write_text("""# Set BEFORE building. React env vars are baked into the build.
REACT_APP_BACKEND_URL=https://fatinpenorhes.online
""")
print("    frontend/ done")


# ============================================================
# 3. MongoDB backup
# ============================================================
print("[3/6] Running mongodump...")
mongo_dest = STAGE / "mongodb_backup"
mongo_dest.mkdir()
dump_dir = mongo_dest / f"mongodump-{STAMP}"
result = subprocess.run(
    ["mongodump", f"--uri={MONGO_URL}", f"--db={DB_NAME}",
     f"--out={dump_dir}", "--quiet"],
    capture_output=True, text=True,
)
if result.returncode != 0:
    print("mongodump failed:", result.stderr)
    sys.exit(1)

(mongo_dest / "RESTORE.md").write_text(f"""# MongoDB Restore Instructions

The dump in `mongodump-{STAMP}/` was taken from database `{DB_NAME}`.

## Restore on the new server

```bash
# 1. Make sure MongoDB is running locally on the new server
sudo systemctl start mongod

# 2. Restore (drops existing collections — careful)
mongorestore \\
  --uri="mongodb://127.0.0.1:27017" \\
  --db=pawn \\
  --drop \\
  ./mongodump-{STAMP}/{DB_NAME}

# 3. Verify
mongosh "mongodb://127.0.0.1:27017"
> use pawn
> db.clients.countDocuments()
> db.contracts.countDocuments()
> exit
```

The expected counts at backup time are in the top-level `collections.txt`.

## Re-dump on this server later

```bash
mongodump --uri="$MONGO_URL" --db=$DB_NAME --out=./backup-$(date +%Y%m%d)
```
""")
print("    mongodb_backup/ done")


# ============================================================
# 4. Collection list
# ============================================================
print("[4/6] Listing collections...")

async def list_colls():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    out = []
    for name in await db.list_collection_names():
        cnt = await db[name].count_documents({})
        out.append((name, cnt))
    client.close()
    return sorted(out)


colls = asyncio.run(list_colls())
collections_txt = STAGE / "collections.txt"
with collections_txt.open("w") as f:
    f.write(f"# Collections in '{DB_NAME}' (snapshot: {STAMP} UTC)\n")
    f.write(f"# Total: {len(colls)} collections, {sum(c for _, c in colls)} documents\n\n")
    for name, cnt in colls:
        f.write(f"{name:<30s} {cnt:>8d} documents\n")
print(f"    collections.txt — {len(colls)} collections")


# ============================================================
# 5. Top-level docs
# ============================================================
print("[5/6] Writing README + DEPLOYMENT guide...")

(STAGE / "README.md").write_text(f"""# Fatin Penhores Pawn System — Full Project Backup

Snapshot: **{STAMP} UTC**
Database: `{DB_NAME}` ({len(colls)} collections, {sum(c for _, c in colls)} documents)

## What's in this archive

```
FatinPenhores_Project_{STAMP}/
├── backend/                  FastAPI server + all Python modules
├── frontend/                 React (CRA + Craco) application
├── mongodb_backup/           mongodump of the live data + RESTORE.md
├── collections.txt           Snapshot of every collection + doc counts
├── README.md                 (this file)
└── DEPLOYMENT.md             Step-by-step deployment guide
```

## Quick start (TL;DR)

```bash
# 1. Setup MongoDB and unpack this zip
unzip FatinPenhores_Full_Project_Backup.zip -d /opt/

# 2. Restore the database
cd /opt/FatinPenhores_Project_{STAMP}/mongodb_backup
mongorestore --uri="mongodb://127.0.0.1:27017" --db=pawn --drop ./mongodump-{STAMP}/{DB_NAME}

# 3. Backend
cd /opt/FatinPenhores_Project_{STAMP}/backend
cp .env.template .env
nano .env          # fill in secrets (see DEPLOYMENT.md for details)
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# 4. Frontend
cd /opt/FatinPenhores_Project_{STAMP}/frontend
cp .env.template .env
nano .env          # set REACT_APP_BACKEND_URL
yarn install
yarn build         # OR: yarn start (for dev)
```

Full step-by-step (Nginx, SSL, Docker, systemd) in **DEPLOYMENT.md**.

## Security

- The `mongodb_backup/` folder contains personal data (BI/passport, phone, address) of ALL clients.
- **Never commit this zip to git.** A `.gitignore` is already included to prevent that.
- Store the zip encrypted (7zip with password, or LUKS volume).
""")

(STAGE / "DEPLOYMENT.md").write_text(f"""# Deployment Guide — Fatin Penhores Pawn System

This is the full step-by-step guide to running the app on your own server.

## 1. Server requirements

- Ubuntu 22.04 LTS (or any Linux with systemd)
- 2 CPU / 4 GB RAM / 20 GB disk minimum
- Open ports 80, 443 to the internet
- A domain name pointed at the server IP (e.g., `fatinpenorhes.online`)

## 2. Install dependencies

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nodejs npm \\
                    mongodb nginx certbot python3-certbot-nginx \\
                    git unzip
sudo npm install -g yarn
sudo systemctl enable --now mongod nginx
```

## 3. Unpack project + restore data

```bash
sudo mkdir -p /opt/fatin-penhores
sudo unzip FatinPenhores_Full_Project_Backup.zip -d /opt/fatin-penhores
cd /opt/fatin-penhores/FatinPenhores_Project_{STAMP}
sudo chown -R $USER:$USER .

# Restore Mongo
cd mongodb_backup
mongorestore --uri="mongodb://127.0.0.1:27017" --db=pawn --drop \\
    ./mongodump-{STAMP}/{DB_NAME}
```

## 4. Backend setup

```bash
cd /opt/fatin-penhores/FatinPenhores_Project_{STAMP}/backend
cp .env.template .env
```

Edit `.env` — **critical fields**:

| Key | What to set |
|---|---|
| `MONGO_URL` | `mongodb://127.0.0.1:27017` (or Atlas URL) |
| `DB_NAME` | `pawn` |
| `CORS_ORIGINS` | `https://fatinpenorhes.online,https://www.fatinpenorhes.online`  ⚠️ **never `*`** |
| `JWT_SECRET` | `openssl rand -hex 32` (or copy from Emergent to keep sessions valid) |
| `WHATSAPP_ENCRYPTION_KEY` | **Copy exactly from Emergent** or lose access to saved WhatsApp token. To generate fresh: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Your admin login |

Install + run:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Test:
uvicorn server:app --host 0.0.0.0 --port 8001
# Visit http://server-ip:8001/api/health → expect 200
```

### Production systemd service

```bash
sudo tee /etc/systemd/system/fatinpenhores-backend.service <<'EOF'
[Unit]
Description=Fatin Penhores Backend
After=network.target mongod.service

[Service]
WorkingDirectory=/opt/fatin-penhores/FatinPenhores_Project_{STAMP}/backend
EnvironmentFile=/opt/fatin-penhores/FatinPenhores_Project_{STAMP}/backend/.env
ExecStart=/opt/fatin-penhores/FatinPenhores_Project_{STAMP}/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8001
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now fatinpenhores-backend
sudo systemctl status fatinpenhores-backend
```

## 5. Frontend setup

```bash
cd /opt/fatin-penhores/FatinPenhores_Project_{STAMP}/frontend
cp .env.template .env
nano .env   # set REACT_APP_BACKEND_URL=https://fatinpenorhes.online

yarn install
yarn build  # produces ./build/ (static files)
```

Serve the static build via Nginx (see next step).

## 6. Nginx + HTTPS

```bash
sudo tee /etc/nginx/sites-available/fatinpenhores <<'EOF'
server {{
    server_name fatinpenorhes.online www.fatinpenorhes.online;

    # React static build
    root /opt/fatin-penhores/FatinPenhores_Project_{STAMP}/frontend/build;
    index index.html;
    location / {{
        try_files $uri $uri/ /index.html;
    }}

    # FastAPI backend
    location /api/ {{
        proxy_pass http://127.0.0.1:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

    client_max_body_size 25M;
}}
EOF
sudo ln -sf /etc/nginx/sites-available/fatinpenhores /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d fatinpenorhes.online -d www.fatinpenorhes.online
```

## 7. Verify

Open https://fatinpenorhes.online:

- Public site renders ✅
- Login at `/login` with the admin credentials ✅
- Dashboard shows correct KPIs ✅
- Finance page → Capital Sources / Expenses / Invoices tabs all show data ✅
- F12 → Console should be clean (no CORS or 401 errors) ✅

## 8. Updates after deployment

Pull new code from your GitHub repo:

```bash
cd /opt/fatin-penhores-app
git pull

# Rebuild frontend
cd frontend && yarn build

# Restart backend
sudo systemctl restart fatinpenhores-backend
```

## 9. Daily backups (already scheduled)

The backend's APScheduler runs `scripts/build_backup.py` daily at 02:00 UTC and
keeps the last 7 snapshots in `/app/backups/`. If you renamed the project root,
adjust the path in `scheduler.py`.

## 10. Object storage caveat

The Emergent object storage (`storage.py`) only works on Emergent's platform.
On a self-hosted server, photos uploaded BEFORE migration won't load. Options:
- Migrate to **AWS S3 / Cloudflare R2** (replace `storage.py`)
- Use **local disk** (uncomplicated but limits scaling)
- Use **MinIO** (self-hosted S3-compatible)

If you'd like help swapping it out, ask the AI for "Replace Emergent storage
with local disk / S3" — it'll generate the drop-in replacement.
""")

(STAGE / ".gitignore").write_text("""# === NEVER commit these — contain PII / secrets ===
.env
.env.*
*.env
node_modules/
__pycache__/
*.pyc
mongodb_backup/
backups/
*.zip
""")

print("    README.md + DEPLOYMENT.md + .gitignore done")


# ============================================================
# 6. Zip everything
# ============================================================
print("[6/6] Creating zip archive...")
if ZIP_PATH.exists():
    ZIP_PATH.unlink()
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for root, dirs, files in os.walk(STAGE):
        # skip caches / node_modules just in case
        dirs[:] = [d for d in dirs if d not in {"__pycache__", "node_modules", ".cache", "build"}]
        for fname in files:
            full = Path(root) / fname
            arc = full.relative_to(OUT_DIR)
            zf.write(full, arc)

shutil.rmtree(STAGE)
size_mb = ZIP_PATH.stat().st_size / 1024 / 1024
print(f"\n=== DONE ===")
print(f"Output: {ZIP_PATH}  ({size_mb:.2f} MB)")
