# 🚚 Migration Guide — Fatin Penhores Pawn System

This document walks you through moving the app from Emergent to your own server,
**without losing data or downtime**.

---

## 📋 Phase 1 — Before you migrate (Preparation)

Do this while still on Emergent. Allow ~1 hour.

### ✅ Step 1.1 — Save the code to GitHub

1. In the Emergent chat, click the **"Save to GitHub"** button (bottom of the chat input).
2. Choose or create a GitHub repository (e.g., `fatin-penhores-app`).
3. **Make the repo PRIVATE** (your business code should not be public).
4. Confirm the push succeeds — you should see all `/app/backend/` and `/app/frontend/` files on GitHub.

### ✅ Step 1.2 — Back up the database

Ask the AI: **"Generate a complete MongoDB backup zip for me to download"**

The AI will create a `.zip` file containing all your data:
- Clients, contracts, payments, items, finance, invoices, audit logs

Save this `.zip` somewhere safe (Google Drive, your laptop, USB stick).
**Keep at least 2 copies in different places.**

### ✅ Step 1.3 — Back up uploaded files (photos & documents)

Ask the AI: **"Export all client documents and item photos into a zip"**

This downloads every photo of cars, motorcycles, electronics, heavy equipment +
client BI/passport scans into a folder.

### ✅ Step 1.4 — Copy your secret keys

You need to copy these values from Emergent's `/app/backend/.env` to your new
server. **They are NEVER stored in GitHub** — you must transfer them manually.

Ask the AI: **"List the env variable names I need to copy (without showing values)"**

You'll get a list like:
```
MONGO_URL                  ← will change on your server
DB_NAME                    ← keep the same
JWT_SECRET                 ← keep the same to not invalidate sessions
WHATSAPP_ENCRYPTION_KEY    ← MUST keep the same (or lose access to saved token)
ADMIN_EMAIL
ADMIN_PASSWORD
```

Write each one down on paper or in a password manager.

---

## 🖥️ Phase 2 — Prepare your server

Your server should have:
- **Linux** (Ubuntu 22.04 LTS recommended)
- **2 CPU cores, 4 GB RAM minimum**
- **20 GB free disk**
- **Docker + Docker Compose installed**
- **MongoDB installed** (since you mentioned your server supports it)
- A **domain name** (e.g., `fatinpenorhes.online`) pointing to the server's IP

### ✅ Step 2.1 — Install Docker (if not already)

```bash
sudo apt update
sudo apt install docker.io docker-compose-v2 git nginx certbot python3-certbot-nginx -y
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

### ✅ Step 2.2 — Clone the code from GitHub

```bash
cd /opt
sudo git clone https://github.com/YOUR-USERNAME/fatin-penhores-app.git
sudo chown -R $USER:$USER fatin-penhores-app
cd fatin-penhores-app
```

### ✅ Step 2.3 — Create the production `.env` files

```bash
nano backend/.env
```

Paste your saved secrets — make sure `MONGO_URL` points to YOUR server's MongoDB:

```
MONGO_URL=mongodb://localhost:27017
DB_NAME=fatin_penhores
JWT_SECRET=<the value you copied>
WHATSAPP_ENCRYPTION_KEY=<the value you copied>
ADMIN_EMAIL=admin@fatinpenhores.tl
ADMIN_PASSWORD=<your admin password>
WHATSAPP_API_VERSION=v22.0
```

For frontend:
```bash
nano frontend/.env
```
```
REACT_APP_BACKEND_URL=https://fatinpenorhes.online
```

---

## 📦 Phase 3 — Restore your data

### ✅ Step 3.1 — Restore MongoDB

Copy your backup zip to the server, unzip, then:
```bash
mongorestore --uri="mongodb://localhost:27017" --db=fatin_penhores ./backup-folder/fatin_penhores
```

Verify:
```bash
mongosh
> use fatin_penhores
> db.clients.countDocuments()
> db.contracts.countDocuments()
```

### ✅ Step 3.2 — Restore uploaded files

Copy your photo/document zip to:
```bash
sudo mkdir -p /var/data/fatinpenhores-uploads
sudo unzip uploaded-files.zip -d /var/data/fatinpenhores-uploads/
```

Update `backend/.env` to point to this folder if the storage code needs it.

---

## 🚀 Phase 4 — Start the app

### ✅ Step 4.1 — Build & run

Ask the AI to **"Generate a Dockerfile and docker-compose.yml for production"**
when you're ready — I'll create these for you.

Then:
```bash
docker compose up -d --build
```

Wait 30 seconds, then test:
```bash
curl http://localhost:8001/api/health     # backend up?
curl http://localhost:3000                # frontend up?
```

### ✅ Step 4.2 — Setup Nginx + HTTPS

```bash
sudo nano /etc/nginx/sites-available/fatinpenhores
```

Paste:
```nginx
server {
    server_name fatinpenorhes.online;

    location /api/ {
        proxy_pass http://localhost:8001/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        proxy_pass http://localhost:3000;
    }
}
```

Enable it & get SSL:
```bash
sudo ln -s /etc/nginx/sites-available/fatinpenhores /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d fatinpenorhes.online
```

### ✅ Step 4.3 — Login & verify

Open https://fatinpenorhes.online → log in with your admin credentials.

Check:
- [ ] Dashboard shows correct totals
- [ ] All clients are present
- [ ] Active contracts visible
- [ ] Photos display correctly
- [ ] Settings → WhatsApp shows "Connected" (token decrypted successfully)
- [ ] Public Warehouse password still works

---

## 🔄 Phase 5 — Ongoing updates (after migration)

The development loop becomes:

```
You → ask me for a change → Emergent builds → You click "Save to GitHub"
                                                       ↓
                                              GitHub repo updated
                                                       ↓
                                       SSH into your server
                                                       ↓
                                  git pull && docker compose up -d --build
                                                       ↓
                                              Live for your customers
```

### Update commands on the server
```bash
cd /opt/fatin-penhores-app
git pull
docker compose up -d --build
```

If something breaks, **roll back instantly**:
```bash
git log --oneline -5            # see last 5 commits
git checkout <good-commit-id>   # roll back to a known-good version
docker compose up -d --build
```

---

## 🆘 Things that won't work after migration (and replacements)

| Feature | Won't work because | Replacement |
|---|---|---|
| Object storage (item photos) | Emergent-hosted | Use local disk or AWS S3 / Cloudflare R2 |
| Emergent LLM Universal Key | Emergent-only | Add your own OpenAI / Anthropic / Gemini key |
| Auto SSL renewal | Was managed | `certbot renew` (cron job — auto with apt) |

---

## 📞 Emergency contacts

- **Server provider**: <your VPS provider's support phone>
- **Domain registrar**: <whoever you bought the domain from>
- **Backups location**: <where you saved the zips>

---

**📌 Tip:** Print this guide and keep it near your server. Migration is much
calmer when you have the checklist in front of you.
