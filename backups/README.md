# Fatin Penhores — Migration Backup

Snapshot taken: **20260705-1834 UTC**

## Files in this folder

| File | Purpose |
|---|---|
| `mongodb-backup-20260705-1834.zip` | Full `mongodump` of the `test_database` database |
| `uploads-backup-20260705-1834.zip` | All client documents & item photos (with `MANIFEST.json`) |
| `env-template.txt` | Structure of the production `.env` — fill in secrets before use |
| `collections.txt` | Counts of every collection at backup time |

## Restore on your own server

```bash
# 1. MongoDB
unzip mongodb-backup-20260705-1834.zip -d ./
mongorestore --uri="mongodb://localhost:27017" --db=test_database ./mongodump-20260705-1834/test_database

# 2. Verify
mongosh
> use test_database
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
