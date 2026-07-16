# Мал тооллого

Private, multi-device livestock management PWA for horse, cattle, sheep/goat, finance, herder, audit, analytics, report, image, and backup workflows.

The repository has a React/Vite frontend and a FastAPI/SQLAlchemy backend. PostgreSQL is the production source of truth, Supabase Storage is private production image storage, Render hosts the API, and Vercel hosts the static PWA.

## Architecture

- `frontend/src/api`: centralized authenticated API client with short-lived access tokens and HTTP-only refresh cookies.
- `frontend/src/offline`: user-owned IndexedDB JSON mutation queue with idempotency and explicit pending/failed/conflict states. Authentication and files are never queued.
- `frontend/src/features`: livestock and owner workflows, real charts, archive/restore, corrections, and exports.
- `backend/app/api`: feature routers and mandatory role dependencies.
- `backend/app/services`: validation, idempotency, storage, and staged backup validation.
- `backend/migrations`: Alembic schema history; production does not call `create_all`.
- `backend/tests`: isolated security, authorization, integrity, report, image, idempotency, and restore tests.

## Local setup

Prerequisites: Python 3.12, Node 22, and PostgreSQL for production-like development. SQLite is supported only for isolated development/testing.

```powershell
cd backend
Copy-Item .env.example .env
python -m pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Set all four one-time `SEED_*_CODE` values before `python -m app.seed`, then remove them from `.env`. The command hashes values with Argon2id and never stores plaintext. Seeded accounts require a code change.

In another terminal:

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

Create `frontend/.env.example` values locally as needed; the only frontend setting is:

```text
VITE_API_URL=http://localhost:8000
```

## Database and migrations

Use a psycopg URL. Plain `postgresql://` and `postgres://` inputs are normalized, but the explicit form is preferred:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres?sslmode=require
```

Commands:

```powershell
cd backend
alembic upgrade head
alembic current
alembic check
alembic revision --autogenerate -m "description"
```

Always review generated migrations. Render runs `alembic upgrade head` as its pre-deploy command.

## Verification

```powershell
cd backend
python -m compileall -q app migrations tests
ruff check app migrations tests
ruff format --check app migrations tests
pytest -q

cd ..\frontend
npm ci --no-audit --no-fund
npm run lint
npm run typecheck
npm test
npm run build
```

The exact results from this implementation run are in [TEST_REPORT.md](TEST_REPORT.md). PostgreSQL and live Supabase checks still require an available service.

## Deployment

### Render

Create the service from `render.yaml`. Configure `DATABASE_URL`, a unique 32+ character `JWT_SECRET`, exact HTTPS `CORS_ORIGINS`, and all Supabase values. Production startup fails on SQLite, wildcard/non-HTTPS CORS, default/short JWT secrets, or missing storage configuration. Run the seed command once using temporary secret values.

### Supabase

Use PostgreSQL with SSL and a private Storage bucket. The service-role key belongs only in Render secrets. Do not expose it through Vite. The API validates and re-encodes images, stores checksums/metadata, and serves authorized signed content. Production storage fails closed; it never falls back to Render disk.

### Vercel

Set the root directory to `frontend`, build command `npm run build`, output `dist`, and `VITE_API_URL` to the Render HTTPS API. The lockfile contains public npm registry URLs. Add the exact Vercel origin to backend `CORS_ORIGINS`.

## Backup and restore

Backups include authentication hashes, registration data, audit rows, and image objects. Store them as sensitive data; archives are not encrypted by the application. Restore requires owner authorization and literal `RESTORE` confirmation. The API checks the versioned manifest, mandatory tables/columns, checksums, archive paths, object set, identities, and foreign keys before deleting rows; it also creates a pre-restore backup. Restore forces reauthentication.

## Offline and PWA behavior

The service worker uses network-first navigation and caches only same-origin static assets; authenticated API responses are not cached. Approved JSON creates can be queued in IndexedDB with a per-user idempotency key. Validation, authorization, server, and version conflicts are shown as failures/conflicts, not success. Edits and image uploads require online mode. Logout preserves the user-owned queue.

Install on iPhone using Safari Share → Add to Home Screen. On Android/desktop use the browser install control or the in-app install button. A banner appears when a new service worker is ready.

## Operations and security

- Check `/health` for process liveness and `/ready` for database plus Alembic revision readiness.
- Rotate credentials through the authenticated code-change/admin rotation endpoints or a controlled deployment procedure.
- Review owner-only audit history after restores, exports, credential changes, and unusual login failures.
- Do not retain one-time seed secrets after seeding.
- Monitor request IDs in API logs when investigating errors.
- If storage or readiness fails in production, fix the dependency; do not enable local fallback.

See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) for release gating and [SECURITY_REVIEW.md](SECURITY_REVIEW.md) for the threat model and remaining limitations.

## External verification status

Automated Playwright verification now passes on Chromium desktop, iPhone-like, and Android-like viewports. PostgreSQL is prepared but BLOCKED locally by missing SCRAM credentials; Supabase Storage is BLOCKED by absent environment secrets. See [FINAL_EXTERNAL_VERIFICATION.md](FINAL_EXTERNAL_VERIFICATION.md) for exact evidence and commands. The repository is a release candidate, not yet production-approved.
