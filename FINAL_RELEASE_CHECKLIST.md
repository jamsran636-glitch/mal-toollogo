# Final Release Checklist

Status values reflect evidence from this run only.

## Security

- PASS — no plaintext production credentials; test fixtures contain documented initial values.
- PASS — DB users, Argon2id, throttling, revocation, DB permission reread.
- PASS — arbitrary audit creation removed and production CORS validated strictly.
- PASS — local authorization and critical security tests.

## Database and audit

- PASS — Alembic exists; empty SQLite upgrade and drift check pass.
- NOT TESTED — empty PostgreSQL upgrade/API suite (Docker engine unavailable).
- PASS — important constraints and atomic mutation/audit behavior implemented/tested.
- PASS — actor, role, UTC time, old/new, reason, request identity fields available.

## Business modules

- PASS — horse pregnancy, age, tree, statistics, CRUD, transfer, archive/restore, images UI/API.
- PASS — cattle full CRUD, ordering/statistics code, female-bull prevention, archive/restore/images.
- PASS — nonnegative census, төлөг/борлон totals, full/evening correction, mortality permission.
- PASS — owner finance/herder workflows with validation and audit.
- PASS — explicit January 1 snapshots, no fabricated history, required charts/toggles.

## Images, backup, offline/PWA

- PASS — local image validation/metadata/privacy implementation and malformed input test.
- NOT TESTED — live Supabase bucket/policy/lifecycle.
- PASS — local backup valid round trip; empty/malformed/traversal/unauthorized cases rejected.
- PARTIAL — distributed DB/object restore uses validation and pre-backup but cannot be one physical transaction.
- PASS — unsafe localStorage queue removed; IndexedDB/idempotency/status implementation tested.
- NOT TESTED — installed PWA on real iPhone/Android/desktop and upgrade behavior.

## Quality and deployment

- PASS — backend: 25 tests, lint, format, compile, SQLite migration/drift.
- PASS — frontend: public npm ci, lint, typecheck, 4 tests, production build.
- FAIL — key Playwright/E2E workflows are not implemented.
- NOT TESTED — remote GitHub Actions, Render, Vercel, Supabase, multi-device concurrency.
- PASS — Render/Vercel/Docker/CI configuration and truthful documentation present.

## Decision

- Critical findings remaining in locally tested code: **0**.
- High-risk external verification gaps: **3** — PostgreSQL execution, live Supabase storage, browser/E2E/device validation.
- Safe to deploy: **NO**.
- Next action: start Docker Desktop or use CI, then run the `backend-postgres` job; proceed through `DEPLOYMENT_CHECKLIST.md` only after it passes.

## 2026-07-16 external gate update

- PASS — Playwright core owner workflow on desktop Chromium.
- PASS — worker visibility and API denials on desktop, iPhone-like, and Android-like Chromium.
- PASS — automated offline shell and no authenticated API cache.
- PASS — npm and pip vulnerability audits are clean after reviewed upgrades.
- PASS — Git `main` initialized with logical history and ignored artifacts.
- BLOCKED — PostgreSQL migration/integration: a local server is reachable but no password was supplied; Docker engine is stopped.
- BLOCKED — live Supabase Storage: environment secrets absent.
- NOT TESTED — physical iPhone/Android/desktop installation and hosted staging.
- PARTIAL — update banner code exists; service-worker two-build update automation is not included.

Decision remains **NO DEPLOYMENT** until both BLOCKED service gates pass.
