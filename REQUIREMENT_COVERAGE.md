# Requirement Coverage

| Area | Status | Evidence / remaining gap |
|---|---|---|
| DB-backed hashed users | PASS | `User`, Argon2id, environment seed, auth tests |
| Throttle/revoke/DB permission reread | PASS | session/login models and auth tests |
| Backend role enforcement | PASS | dependencies and matrix/owner denial tests |
| Alembic/no production create_all | PASS | initial migration, upgrade/check executed |
| PostgreSQL integration | NOT TESTED | CI job configured; local Docker engine unavailable |
| Atomic server audit | PASS | add-only audit + rollback/actor/old-new tests |
| Horse API/UI core workflows | PASS | create/edit/archive/restore/transfer/history/images UI and tests |
| Horse ordering/pregnancy/age | PASS | domain implementation and tests |
| Cattle API/UI workflows/invariants | PASS | full patched-state validation, archive/restore/images UI/tests |
| Census/evening/correction/totals | PASS | UI/API and tests; categories documented non-overlapping |
| Owner mortality/worker denial | PASS | UI/API and 403 test |
| Finance/herder CRUD | PASS | owner UI/API, archive/restore/audit |
| Real snapshot analytics | PASS | explicit January 1 model/UI; unknown values are null |
| Required dashboard widgets/toggles | PASS | Recharts widgets and persisted preferences |
| Secure image processing | PASS locally | malformed/spoof test; live Supabase NOT TESTED |
| Reports | PARTIAL | Excel/PDF API and file tests pass; UI filter controls absent |
| Backup validation/round trip | PASS locally | valid, empty, malformed, traversal, unauthorized tests |
| Distributed storage restore atomicity | PARTIAL | validate-first/pre-backup; no cross-system transaction |
| IndexedDB/idempotency/conflicts | PASS for approved creates | edits/files intentionally online-only |
| Safe service worker/update/install UI | PASS in code | real browser behavior NOT TESTED |
| Portable lock and CI | PASS locally | clean npm install passes; remote CI NOT TESTED |
| E2E/browser/device suite | FAIL | not implemented in this run |
| Live Render/Vercel/Supabase | NOT TESTED | deployment checklist required |

## External verification update

| Requirement | Status | Evidence |
|---|---|---|
| Core owner browser workflow | PASS | Chromium Playwright journey |
| Worker browser restrictions | PASS | desktop/iPhone-like/Android-like projects |
| PWA offline shell/no API cache | PASS | all three Playwright projects |
| Update banner | PARTIAL | implementation present; two-build automated test absent |
| Physical installability | NOT TESTED | manual device checklist |
| PostgreSQL | BLOCKED | reachable local service, no SCRAM credential; CI/script ready |
| Supabase lifecycle | BLOCKED | no secrets; unique-prefix test/workflow ready |
| Dependency security | PASS | npm and final pip audits clean |
| Git history | PASS | initialized `main`, logical commits, ignored artifacts |
