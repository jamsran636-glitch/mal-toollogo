# Final External Verification

Date: 2026-07-16  
Status: **release candidate — external service credentials still required**

## PostgreSQL evidence — BLOCKED

- Docker CLI 29.4.2 is installed, but `docker version` could not reach `dockerDesktopLinuxEngine`; Windows service `com.docker.service` is stopped.
- Local `postgresql-x64-18` is running and `pg_isready -h localhost -p 5432` returned `accepting connections`.
- The server requires SCRAM authentication. No `PGPASSWORD`, `pgpass.conf`, `DATABASE_URL`, or `POSTGRES_TEST_URL` was available. A passwordless `psql -w` correctly failed with `fe_sendauth: no password supplied`.
- Therefore no PostgreSQL migration or API result is marked PASS.
- `.github/workflows/ci.yml` has a PostgreSQL 16 service, Alembic empty upgrade, drift check, and full pytest job.
- `scripts/verify_postgres.ps1` is guarded to accept only a disposable PostgreSQL URL whose database name contains `mal_test`, `integration`, or `_test`.
- PostgreSQL-only concurrent idempotency coverage is present and skipped explicitly on SQLite.

Required next command:

```powershell
$env:POSTGRES_TEST_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/mal_test'
.\scripts\verify_postgres.ps1
```

Alternatively start Docker Desktop, wait for `docker version` to show a Server section, and run the GitHub-equivalent PostgreSQL container job.

## Supabase Storage evidence — BLOCKED

The required `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET` variables were absent. No secrets were invented or logged, and no live claim is made.

Ready-to-run evidence:

- `backend/tests/test_supabase_live.py` is explicitly skipped when credentials are absent.
- With credentials it checks private bucket readiness, upload, authenticated read, signed URL, public denial, replacement, and cleanup under a unique `integration-tests/` key.
- `.github/workflows/external-storage.yml` is a manual, secret-gated workflow.
- `/ready/storage` performs a real bucket lookup and rejects public buckets; `/ready` remains database/schema readiness only.
- Production continues to fail closed without configured storage.

## Playwright evidence — PASS

Command: `npm run test:e2e`

Result: **16 passed, 2 intentionally skipped, 0 failed in 23.9s**.

- Chromium desktop: owner full workflow, all worker menus, API denials, and PWA offline test passed.
- iPhone 13-like Chromium viewport: three worker layouts/menus, API denials, and PWA offline test passed.
- Pixel 7-like Chromium viewport: three worker layouts/menus, API denials, and PWA offline test passed.
- The two skips are the mutating owner journey on the two mobile viewport projects; it runs once on desktop to avoid duplicate unique records in the shared isolated database.

The owner journey covers horse group/create/edit/transfer/archive/restore, cattle create/edit/archive/restore, full census/correction/evening census, income/expense, herder create/edit, analytics widgets/toggle, audit, Excel export, backup download, and malformed restore rejection. Worker tests verify role-only cards and direct API denial, including sheep-worker mortality denial.

Browser execution found and fixed four real defects: first-install service-worker reload during login, archive form validation mismatch, analytics response-contract mismatch, and incomplete first offline precache.

## PWA evidence — PASS for automated Chromium; physical devices NOT TESTED

- Manifest loaded successfully in all three Playwright projects.
- Service worker registered and controlled the page.
- Offline indicator appeared.
- Offline reload rendered the application shell after hashed JS/CSS precaching.
- Cache inspection confirmed no `/api/` request was stored.
- Update code path is implemented, but a two-build update-banner automation is not yet present.
- Installability on physical Safari/Chrome remains manual and NOT TESTED.

Manual checklist:

- [ ] iPhone Safari: Share → Add to Home Screen; launch standalone; login/refresh; offline shell; update.
- [ ] Android Chrome: install prompt; launch standalone; login/refresh; offline shell; update.
- [ ] Desktop Chrome/Edge: install; launch; update; uninstall/reinstall.

## Deployment evidence — PASS for local/static validation; hosting NOT TESTED

- Public `npm ci`, frontend lint/typecheck/unit/build, and Playwright production-preview tests pass.
- Render config has pre-deploy Alembic migration, `/ready`, strict production settings, and no local production storage fallback.
- Vercel config has SPA rewrite; root/build/output/environment requirements are documented.
- `scripts/deployment_dry_run.ps1` validates compile/lint/format, frontend CI commands, lockfile registry, build, and manifest.
- Production configuration tests reject SQLite, short JWT secret, wildcard/non-HTTPS CORS, and missing storage credentials.
- Live Render, Vercel, Supabase, DNS/TLS, and cross-site refresh-cookie behavior are NOT TESTED.

## Dependency evidence

- `npm audit --omit=dev --audit-level=high`: **0 vulnerabilities**.
- Initial `pip-audit` found advisories in old pins. PyJWT, python-multipart, Pillow, pytest, and FastAPI/Starlette were upgraded and regression-tested.
- Final `pip-audit -r requirements.txt`: **No known vulnerabilities found**.

## Final recommendation

Keep status at **release candidate**. Do not deploy family data until PostgreSQL verification and live private Supabase lifecycle pass. After those pass, deploy to a staging Render/Vercel pair and complete the physical-device checklist before production approval.
