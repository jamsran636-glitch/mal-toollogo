# Deployment Checklist

## Before release

- [ ] PASS locally: backend lint, format, compile, 25 tests.
- [ ] PASS locally: Alembic empty SQLite upgrade and drift check.
- [ ] PASS locally: public `npm ci`, frontend lint, typecheck, 4 tests, build.
- [ ] Run and PASS GitHub `backend-postgres` job.
- [ ] Run and PASS Playwright/E2E suite (not yet implemented).
- [ ] Create private Supabase Storage bucket and verify upload/read/replace/restore lifecycle.
- [ ] Verify Supabase PostgreSQL SSL/pooler URL with `alembic upgrade head`.
- [ ] Configure Render secrets: database, strict CORS, unique JWT secret, Supabase URL/key/bucket.
- [ ] Configure Vercel `VITE_API_URL` and exact Render/Vercel production origins.
- [ ] Run one-time seed with temporary secret values; remove those values immediately.
- [ ] Rotate all initial codes at first login.
- [ ] Confirm `/health` and `/ready` on Render.
- [ ] Confirm owner/three worker access matrix against deployed API.
- [ ] Confirm HttpOnly Secure refresh rotation/logout on Safari and Chrome.
- [ ] Confirm private image URLs cannot be read unauthenticated.
- [ ] Download, protect, and restore a staged backup; confirm forced reauthentication.
- [ ] Install PWA on iPhone, Android, and desktop; test update and offline shell.
- [ ] Configure log/alert retention and backup retention/encryption.
- [ ] Add CSP and security headers after deployed compatibility test.

## Release command sequence

```text
cd backend
alembic upgrade head
python -m app.seed       # first deployment only, with temporary SEED_* secrets
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Vercel uses `npm ci && npm run build` from `frontend`, output `dist`.

Current safe-to-deploy decision: **NO** until all unchecked external/integration gates above pass.

## Commands prepared for blocked gates

```powershell
# Disposable PostgreSQL database only
$env:POSTGRES_TEST_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/mal_test'
.\scripts\verify_postgres.ps1

# Full local non-external dry run
.\scripts\deployment_dry_run.ps1
```

For Supabase, configure repository secrets `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`, ensure the bucket is private, then manually dispatch **Live Supabase Storage Verification**. The workflow uses a unique test prefix and deletes its object.
