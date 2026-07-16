# Test Report

Date: 2026-07-15

## Executed and passed

| Area | Command | Result |
|---|---|---|
| Backend compile | `python -m compileall -q app migrations tests` | PASS |
| Backend lint | `ruff check app migrations tests` | PASS |
| Backend format | `ruff format --check app migrations tests` | PASS |
| Backend behavior | `pytest -q` | PASS — 25 tests, final run 7.94s |
| SQLite migration | `alembic upgrade head` | PASS |
| Schema drift | `alembic check` | PASS — no new operations |
| Public lock install | `npm ci --no-audit --no-fund` | PASS — 236 packages, 17s |
| Frontend lint | `npm run lint` | PASS |
| Frontend typecheck | `npm run typecheck` | PASS |
| Frontend unit tests | `npm test` | PASS — 3 files, 4 tests |
| Frontend production build | `npm run build` | PASS — 2,343 modules |

Backend coverage includes account hashing/login/lockout/disable/expiry/revocation/permission reread, authorization, audit actor/old-new/atomic rollback, April 1 age classes, pregnancy/tree/transfer/archive/restore, cattle full-state validation, census totals/correction/mortality denial, finance/snapshots/preferences, idempotency, valid/empty/malformed/traversal backup behavior, image spoof rejection, report file signatures, and worker export denial.

Frontend coverage includes role-filtered navigation, currency, IndexedDB user/idempotency storage, and auth-path queue rejection. Typechecking/lint/build provide full source compilation but are not substitutes for browser workflow coverage.

## Not executed

- PostgreSQL migration/API run: attempted with `docker run postgres:16`, but Docker Desktop Linux engine was not running (`dockerDesktopLinuxEngine` pipe missing).
- Live Supabase Storage integration.
- Playwright/E2E owner and worker workflows.
- Real iPhone/Android/desktop PWA install, offline shell, refresh-cookie, and upgrade behavior.
- Remote GitHub Actions, Render, or Vercel deployment.

## Build note

Vite emitted a non-fatal chunk-size warning: the main JS chunk is 624.03 kB before gzip (183.30 kB gzip). Functional build status is PASS; code splitting remains a performance improvement.

## External-gate run — 2026-07-16

| Gate | Result |
|---|---|
| Backend with fixed dependency pins | PASS — 31 passed, 2 skipped, 8.03s |
| Backend Ruff check/format/compile | PASS |
| Frontend lint/typecheck/unit/build | PASS — 3 files, 4 tests; 2,343 modules |
| Playwright all projects | PASS — 16 passed, 2 intentional skips, 23.9s |
| PWA offline/no API cache | PASS — desktop, iPhone-like, Android-like Chromium |
| npm production audit | PASS — 0 vulnerabilities |
| pip audit | PASS — no known vulnerabilities after reviewed upgrades |
| PostgreSQL | BLOCKED — server reachable, SCRAM credential absent |
| Supabase Storage | BLOCKED — required variables absent |
| Physical devices | NOT TESTED |

The FastAPI test client emits one Starlette deprecation warning recommending future migration from `httpx` to `httpx2`; it does not fail current tests.
