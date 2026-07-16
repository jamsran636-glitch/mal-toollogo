# Current State Audit

Audit date: 2026-07-15  
Repository directory: `C:\Users\jamsranjamts\Downloads\mal-toollogo-final`  
Scope: diagnosis only; no production source was changed.

## A. Executive summary

**Current state: partially implemented.**

**Confidence: high.** Every application, configuration, workflow, test, and documentation file in this small repository was inspected. The backend was compiled/imported and exercised with the repository smoke scripts plus isolated targeted API checks. The frontend was typechecked and built. Confidence is not “very high” because no live PostgreSQL, Supabase, Render, Vercel, real mobile browser, or multi-device environment was available.

This is not an empty repository or a scaffold. It contains real FastAPI/SQLAlchemy endpoints, a real React UI, local database persistence, JWT authentication, audit rows, image processing, reports, backup/restore code, and a PWA shell. It is also not production-ready. Required workflows are missing from the UI and/or API, data integrity checks can be bypassed, an incomplete backup can erase the database, audit recording is not atomic, the static credentials are unsuitable for production, analytics history is not real history, offline sync is unsafe, and the checked-in npm lockfile prevents the documented CI/Vercel install path in the audited environment.

**Deployment verdict: unsafe to deploy.**

## B. Repository structure and actual stack

The supplied directory is **not a Git checkout**. `git status --short --branch` returned:

```text
fatal: not a git repository (or any of the parent directories): .git
```

As a result, commit history, branch state, tracked/untracked status, and whether files differ from `jamsran636-glitch/mal-toollogo` could not be verified.

### Important files

| Path | Purpose |
|---|---|
| `backend/app/main.py` | Entire FastAPI application and all endpoints in one file |
| `backend/app/models.py` | SQLAlchemy models |
| `backend/app/schemas.py` | Pydantic request/response models |
| `backend/app/auth.py` | Four hardcoded users, JWT creation/validation, role dependencies |
| `backend/app/audit.py` | Audit serialization and insertion |
| `backend/app/database.py` | Engine/session setup |
| `backend/app/config.py` | Environment settings and defaults |
| `backend/smoke_test*.py` | Four executable assertion scripts; no pytest suite |
| `frontend/src/App.tsx` | Almost the entire React UI (103 dense lines) |
| `frontend/src/main.tsx` | React bootstrap and production service-worker registration |
| `frontend/src/styles.css` | All UI styling |
| `frontend/public/manifest.webmanifest` | PWA manifest |
| `frontend/public/sw.js` | Cache-first service worker |
| `frontend/public/icon-*.png` | PWA icons; visually verified as a calf |
| `.github/workflows/ci.yml` | Backend smoke scripts and frontend build workflow |
| `render.yaml` | Render backend service definition |
| `frontend/vercel.json` | SPA rewrite for Vercel |
| `README.md` / `FINAL_VERIFICATION.md` | Deployment and claimed verification notes |

### Actual technology stack

| Layer | Actual stack |
|---|---|
| Frontend | React 19.2.7, TypeScript 7.0.2, Vite 8.1.4, Lucide React 1.24.0, plain CSS |
| Backend | Python 3.12, FastAPI 0.116.1, Uvicorn 0.35.0, Pydantic Settings 2.10.1 |
| ORM/database | SQLAlchemy 2.0.43; SQLite by default; PostgreSQL intended through psycopg 3.2.10 |
| Authentication | Hardcoded users plus signed HS256 JWT bearer tokens |
| Images | Pillow processing; Supabase Storage REST call when configured, otherwise local files |
| Reports | openpyxl XLSX and ReportLab PDF |
| PWA | Handwritten web manifest and service worker; no Workbox/Vite PWA plugin |
| Deployment | Vercel frontend, Render backend, Supabase PostgreSQL/Storage by configuration only |
| CI | GitHub Actions, Python 3.12 and Node 22 |

No Alembic/migration directory, user table, package-level backend test framework, browser tests, end-to-end tests, API version migrations, or infrastructure validation scripts exist.

Diagnostic runs created `frontend/node_modules`, `frontend/dist`, SQLite test databases, and test upload folders. They were not deleted because the audit instructions explicitly prohibited deletion. The package lockfile was not intentionally rewritten; the successful fallback install used `--package-lock=false`.

## C. What really works

Only the following items were verified by execution or direct output validation:

- Backend source compiles and `app.main` imports successfully under Python 3.12.13 with the pinned requirements.
- All four required username/code combinations return HTTP 200 and a JWT in isolated FastAPI `TestClient` checks.
- The backend access matrix is enforced for the four module access endpoints: owner gets all four; horse, cattle, and sheep workers get only their own livestock module. Non-owner requests to audit, herder, and finance owner endpoints return HTTP 403.
- Horse group creation, horse creation, April 1 age calculation, horse statistics, foal indentation, archive flags, group transfer records, and owner audit reads execute in the Phase 3/API checks.
- A worker group update produced an audit row containing the correct `username`, `role`, action, timestamp, and JSON old/new values.
- Cattle creation and cattle statistics execute.
- Full and evening small-livestock count rows can be created and read; sheep-worker mortality creation is blocked with HTTP 403.
- Owner finance income/expense creation and current-year profit calculation execute.
- Owner-only herder creation/listing executes at the API level.
- Horse image upload accepts a real PNG, writes WebP main/layout images, and returns URLs.
- XLSX, PDF, and ZIP backup endpoints return successful responses in the Phase 7 script.
- A valid database backup restored its backed-up rows in a targeted round-trip check.
- File-backed SQLite data was visible through a separate SQLite connection after API commit, confirming local on-disk persistence.
- The PWA manifest parses as JSON; icon files are valid 192×192, 512×512, and 180×180 PNGs. The icon was visually verified as a calf.
- Frontend standalone typecheck passes.
- Frontend production build passes and emits `index.html`, hashed JS/CSS, the manifest, service worker, and all icons.

These checks do **not** prove production PostgreSQL behavior, Supabase image persistence, multi-device concurrency, Vercel/Render deployment, browser installation, background sync, or long-term data correctness.

## D. What does not work

### Exact executed failures

1. The documented/CI frontend install command failed:

```text
npm error code ETIMEDOUT
npm error network request to https://packages.applied-caas-gateway1.internal.api.openai.org/.../vite-8.1.4.tgz failed
```

The lockfile resolves packages to a private/internal artifact hostname. Retrying with only the public registry host produced:

```text
404 Not Found - GET https://registry.npmjs.org/artifactory/api/npm/npm-public/vite/-/vite-8.1.4.tgz
```

The code could be built only after `npm install --package-lock=false --registry=https://registry.npmjs.org`, which is not the checked-in CI command.

2. `backend/smoke_test.py` reached and printed `PHASE 2 SMOKE TEST: PASS`, then exited 1 on Windows:

```text
PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: '...\phase2_test.db'
```

3. An unchanged temporary copy of `backend/smoke_test_phase456.py` reached and printed `PHASE 4-6 SMOKE TEST: PASS`, then exited 1 for the same open-SQLite-file cleanup error.

4. `sqlite:///:memory:` is broken with the current engine configuration. Import creates tables on one connection, while a request can receive another connection:

```text
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: audit_logs
```

### Confirmed functional failures

- A horse created with `current_status="PREGNANT"` exists in `status_filter=ALL` but disappears from the main tree and statistics: targeted output was `pregnant_in_all_list=1`, `pregnant_in_tree=0`, `statistics_total=0`.
- A small-livestock census with `sheep_male=-5` is accepted with HTTP 200 and returns a negative sheep total.
- `hogget` (`төлөг`) and `yearling_goat` (`борлон`) are displayed and stored but are not added by `small_count_dict()` to total/adult stock. The repository Phase 4–6 fixture enters 4 төлөг and 3 борлон yet asserts total 58, the value that omits them.
- A male breeding bull can be patched to `sex="FEMALE"` while `is_bull=true`; the API accepted this invalid state with HTTP 200.
- An authenticated worker can submit an arbitrary action to `POST /api/v1/audit`, including with no module, and the server stores it as an audit event.
- A ZIP containing only `data.json` with `{}` is accepted by backup restore and deletes all business rows. The targeted check ended with `empty_backup_restore=ACCEPTED_AND_WIPED_ROWS`.
- Local image URLs under `/uploads/...` are accessible without authentication.
- The frontend exposes no horse edit, horse restore, transfer history, cattle edit, cattle restore, cattle image upload, sheep mortality, census edit, finance edit, herder create/edit, or backup-restore workflow.
- The analytics UI has no animal-growth widget and no show/hide checkboxes. Its “pie” is styled text pills, not a pie chart.
- Offline queued `FormData` cannot be serialized to localStorage. Network-failed mutations resolve as `{offline:true}`, which callers generally treat as success. There is no idempotency key, conflict handling, or durable per-user operation state.

## E. Placeholder, fake, or overstated implementations

No literal `TODO` or `FIXME` markers were found in application source. The following behaviors are nevertheless placeholder-like or misleading:

| Path | Evidence |
|---|---|
| `backend/app/main.py:804` | `/system/production-check` reports `"pwa": true` as a constant and labels database/storage from configuration strings; it does not test PWA assets, database connectivity, schema state, Supabase reachability, bucket existence, or write access. |
| `backend/app/main.py:529` | “Growth” is reconstructed from current horse/cattle birth years. It is not January 1 historical inventory, ignores animals no longer present in the active query, and emits zero small-livestock history before the current year. |
| `frontend/src/App.tsx:94` | The required annual-growth result is never rendered. “This year profit pie” is not a chart. Widget visibility checkboxes do not exist. |
| `frontend/src/App.tsx:34` | A failed non-GET fetch returns a success-shaped object after queueing. Callers close dialogs or show success without a confirmed server commit. |
| `frontend/src/App.tsx:23` | Offline queue is a JSON array in localStorage; `FormData` bodies become unusable objects, auth/login can be queued, and logout clears pending operations. |
| `frontend/src/App.tsx:102` | Footer claims `Version 1.0 — Production PWA` despite the unresolved security, sync, and deployment blockers. |
| `README.md:1` | Calls the app “Production PWA v1.0” and states final tests succeeded without the qualifications found here. |
| `FINAL_VERIFICATION.md:10` | Claims backup→restore round-trip passed, but `smoke_test_phase7.py` only downloads a backup and never calls restore. A custom audit check verified a normal round trip, but also proved an empty backup wipes data. |
| `backend/app/main.py:607` | Any Supabase upload exception is swallowed and silently falls back to local disk, making a broken production storage configuration appear successful. |

## F. Requirement coverage matrix

| Requirement | Status | Evidence | Relevant file paths |
|---|---|---|---|
| Four required login accounts | Partial | All four logins return 200, but credentials are plaintext constants; three use `00000000`. | `backend/app/auth.py:33`, `backend/smoke_test.py` |
| Backend module authorization | Complete | Executed access matrix returned expected 200/403 results; owner-only audit/herder/finance checks also passed. | `backend/app/auth.py:110`, `backend/app/main.py:210` |
| Horse belongs to a stallion group | Complete | Non-null FK and create-time group validation; group creation/horse creation executed. | `backend/app/models.py:48`, `backend/app/main.py:150` |
| Horse fields and no visible name | Partial | Core fields exist and no name field exists. Only main/layout URLs are stored; original detail-image records are not retained. | `backend/app/models.py:44`, `frontend/src/App.tsx:64` |
| Horse age advances April 1 and age classes | Complete | Traced date boundary logic and class mapping; smoke data returned expected age behavior. | `backend/app/main.py:66` |
| Horse list ordering and foal indentation | Partial | Stallion/mare/foal/remaining order is coded and foal indentation executed. Living `PREGNANT` horses are excluded from tree/stats. | `backend/app/main.py:376` |
| Horse group transfer current list/history | Partial | Current `group_id`, transfer table, reason/user/time and endpoint work in backend. No transfer history UI; group changes only through prompt-entered raw UUID. | `backend/app/main.py:321`, `frontend/src/App.tsx:58` |
| Horse archive, explanation, abnormal mortality, restore | Partial | Backend archive/restore and audit exist; UI exposes archive only for currently visible active horses and exposes no archive list/restore. | `backend/app/main.py:342`, `frontend/src/App.tsx:56` |
| All horse edits audited | Partial | Create/update/archive/restore/transfer are audited. Image old values are omitted; audit commit is separate; general edit UI is absent. | `backend/app/main.py:305`, `backend/app/audit.py:17` |
| Cattle fields and age classes | Partial | Core model/classification exists. Image URLs are omitted from `cattle_dict`; frontend has no cattle image/detail/edit UI. | `backend/app/models.py:85`, `backend/app/main.py:408` |
| Cattle ordering | Partial | Category sort exists (bulls, cows with calves, females, males), but no dedicated ordering regression test was present. | `backend/app/main.py:420` |
| Cattle archive/abnormal mortality/restore | Partial | Archive exists and is audited. Restore does not exist. UI click immediately initiates archive rather than opening details. | `backend/app/main.py:460`, `frontend/src/App.tsx:75` |
| Cattle data integrity | Broken | Update accepts female bull state and does not revalidate mother, self-parenting, sex values, or birth-year bounds. | `backend/app/schemas.py:184`, `backend/app/main.py:450` |
| Full sheep/goat census fields | Broken | Fields are present, but negative values are accepted and төлөг/борлон do not contribute to computed totals/adult total. | `backend/app/schemas.py:197`, `backend/app/main.py:469` |
| Evening census, no mortality | Complete | Evening schema/UI only submit totals/note; no loss input is part of the evening form. | `frontend/src/App.tsx:85`, `backend/app/main.py:486` |
| Sheep worker cannot register mortality | Complete | Endpoint uses owner dependency; executed sheep-worker request returned 403. | `backend/app/main.py:494`, `backend/smoke_test_phase456.py` |
| Census edit audit | Missing | No census update/delete endpoint or UI exists. | `backend/app/main.py:477` |
| Module summary boxes | Partial | Horse/cattle and sheep boxes are rendered. Horse totals omit pregnant animals; sheep totals can be invalid. | `frontend/src/App.tsx:61`, `frontend/src/App.tsx:84` |
| Separate herder records, owner only | Partial | Model and owner-only list/create/update API exist and create/list executed. UI is read-only and does not separate management screens by module. | `backend/app/main.py:675`, `frontend/src/App.tsx:102` |
| Unified income/expense and categories | Partial | Owner can create/list and ₮ formatting renders. Date is editable/required rather than server-automatic; categories/modules are not server-enforced; no edit/delete. | `backend/app/main.py:501`, `frontend/src/App.tsx:93` |
| Default analytics dashboard | Partial | Counts, current finance, mortality, expense, balance, and adult male payloads exist. Historical growth is fabricated, growth is not rendered, no real pie, and no checkboxes exist. | `backend/app/main.py:514`, `frontend/src/App.tsx:94` |
| Every required mutation auditable | Broken | Some existing mutations write old/new/user data, but required edit routes are absent, image old state is missing, client audit actions are accepted, and business/audit commits are not atomic. | `backend/app/audit.py:17`, `backend/app/main.py:230` |
| Image upload and combined layout | Partial | Horse image processing executed. Cattle backend code is untested and its URLs are omitted from cattle responses/UI. Detail images are not modeled. | `backend/app/main.py:638`, `backend/app/main.py:658` |
| Reports | Partial | XLSX/PDF endpoints execute; reports are minimal/raw and omit several business areas. | `backend/app/main.py:698` |
| Backup/restore | Broken | Valid local DB round trip worked, but `{}` backup is accepted and wipes rows; image restore is non-transactional and Supabase objects are not included. | `backend/app/main.py:728` |
| Offline sync | Broken | localStorage queue exists but cannot safely handle files, duplicates, conflicts, logout, validation failures, or login. | `frontend/src/App.tsx:23` |
| Installable multi-device PWA | Partial | Build, manifest, SW, icons and registration exist. No browser install/offline navigation audit was run; sync is unsafe and iOS/Android behavior is unverified. | `frontend/src/main.tsx:6`, `frontend/public/sw.js` |
| Central PostgreSQL/Supabase persistence | Not tested | Configuration paths exist; only file-backed SQLite was executed. | `backend/app/config.py`, `render.yaml` |
| Vercel/Render deployment | Broken | Config files exist, but `npm ci` cannot use the internal lock URLs and there are no migrations/live-service checks. | `frontend/package-lock.json`, `.github/workflows/ci.yml`, `render.yaml` |

## G. Security findings

### Authentication and password handling

- **Critical:** all users and codes are plaintext in `backend/app/auth.py`. The owner code is exposed in source and three worker accounts share `00000000`.
- There is no user table, password hashing, credential rotation workflow, disabled-account state, failed-login throttling, lockout, MFA, or password reset.
- Every deployment receives the same credentials unless source is changed.

### JWT/session

- Tokens live for 43,200 minutes (30 days) by default and there is no revocation, refresh rotation, session table, or token version.
- `get_current_user()` trusts the signed `role` and `modules` claims and does not re-read current server-side permissions or confirm the account still exists.
- Development falls back to `change-this-in-production`. Render generates `JWT_SECRET`, which is good for that specific deployment path, but any other production start without an override uses the known default.
- The frontend stores bearer tokens in localStorage, increasing token theft impact from any XSS.

### Authorization

- Positive finding: module and owner dependencies are applied to the reviewed business routes and the tested access matrix passed.
- The client-side menu restriction is not the only control; backend 403 enforcement exists.
- `POST /api/v1/audit` lets any authenticated user create arbitrary audit actions, and a null module bypasses its module-membership check. This damages audit-log integrity even though the server still supplies username/role.

### Secrets and CORS

- `.env` is ignored and examples use placeholders; no Supabase service key was found committed.
- `CORS_ORIGINS="*"` is supported by configuration. Credentials are disabled in that mode, but bearer-token requests from any origin would still be accepted. Production should reject wildcard origins.
- Render requires `CORS_ORIGINS` as a manual secret. If omitted, the backend defaults to localhost and the Vercel app will fail cross-origin requests.

### File upload/storage

- Image content is decoded and verified, count is capped at eight, individual raw size is capped at 10 MB, dimensions are downscaled, and output is re-encoded. These are useful controls.
- The local file route has no authentication. This was executed and confirmed.
- Path containment uses string `startswith`, not `Path.is_relative_to`; sibling-prefix paths are unsafe as a general containment pattern.
- Supabase errors are swallowed and silently fall back to Render local disk, which is ephemeral and can lose images on restart/deploy.
- Public Supabase URLs are constructed without verifying that the bucket is intentionally public.

### Backup/restore

- **Critical:** restore validates only that provided table names are a subset of expected names. It does not require every table. An empty object therefore passes, commits table deletion, and returns 200.
- Database restore commits before image extraction and before the restore audit event. Database, image files, and audit history are not one atomic operation.
- Existing local files absent from a backup are not removed; mixed old/new image state remains.
- Supabase objects are not backed up; only database URLs and local fallback files are included.
- Backup ZIPs contain full audit data and herder registration numbers without encryption.
- Restoring explicit integer IDs does not reset PostgreSQL sequences, a risk for subsequent audit/transfer inserts on cross-database restore.

## H. Data model findings

### Models present

- `AuditLog`
- `HorseGroup`
- `Horse`
- `HorseGroupTransfer`
- `Cattle`
- `SmallLivestockCount`
- `SmallLivestockLoss`
- `FinanceEntry`
- `Herder`

### Missing or weak relationships and constraints

- No `User`, credential, session, role, or permission model.
- No immutable inventory snapshot/event model capable of January 1 historical analytics.
- No image/detail-image child table, upload metadata, checksums, or ownership/privacy state.
- No cattle history table and no restore state transition.
- No census/finance edit history entity; only generic serialized audit text.
- No offline operation/idempotency table.
- `sex`, status, module, finance category, count type, and livestock module are unconstrained strings at the database level.
- Census values have no nonnegative `CHECK` constraints.
- Census `(count_type, count_date)` is not unique, so multiple “current” rows may exist without an explicit correction/version rule.
- Parent links prevent direct self-parenting for horse creation/update but do not prevent longer ancestry cycles. Cattle update does not even revalidate direct self/sex rules.
- SQLite foreign-key enforcement is not explicitly enabled, so local behavior can hide PostgreSQL FK failures.

### Migration status

There are no migrations. `Base.metadata.create_all(bind=engine)` executes at import time. It can create missing tables but cannot safely evolve columns, constraints, indexes, enum semantics, or data on an existing production database. Schema state is therefore not reproducible or reviewable.

### Persistence and integrity risks

- File-backed SQLite persistence across requests/connections was verified.
- PostgreSQL persistence, pooling, SSL, concurrent writes, transaction isolation, and Supabase session-pooler compatibility were not tested.
- Copying a standard Supabase `postgresql://...` URL may select SQLAlchemy's psycopg2 driver, which is not installed; the example correctly uses `postgresql+psycopg://...`, but the README does not emphasize this conversion.
- Most mutation handlers commit the business row first and call `write_audit()` afterward, where a second commit occurs. A crash/audit insert failure leaves unaudited business data.
- `create_all` runs during module import, making application startup depend on immediate database availability and DDL permission.

## I. Build and test results

| Command | Result | Summary |
|---|---|---|
| `git status --short --branch` | Fail | Directory has no `.git`. |
| `uv run --python 3.12 --with-requirements requirements.txt python -m compileall -q app` | Pass | Backend compiled without syntax errors. |
| Isolated `python -c "import app.main"` | Pass | Printed `BACKEND_IMPORT_PASS 1.0.0`. |
| `python smoke_test.py` | Assertions pass, process fail | Printed Phase 2 pass, then WinError 32 deleting open DB. Four logins and basic role checks passed. |
| `python smoke_test_phase3.py` in isolated directory | Pass | Printed `PHASE3_SMOKE_TEST_PASS`. |
| Unchanged isolated `python smoke_test_phase456.py` | Assertions pass, process fail | Printed Phase 4–6 pass, then WinError 32 deleting open DB. |
| `python smoke_test_phase7.py` in isolated directory | Pass | Printed `PHASE 7 SMOKE TEST: PASS`. |
| Targeted access/audit/persistence/restore checks | Pass as diagnostic | Confirmed access matrix, old/new identity, local persistence, normal restore, and the documented integrity vulnerabilities. |
| `npm ci --prefer-offline --no-audit --no-fund` | Fail | ETIMEDOUT fetching private/internal Vite tarball. |
| `npm ci --registry=https://registry.npmjs.org --replace-registry-host=always` | Fail | Lockfile path becomes an invalid npmjs `/artifactory/...` URL (404). |
| `npm install --package-lock=false --registry=https://registry.npmjs.org` | Pass | Installed 25 packages for diagnostic fallback. |
| `npm ls --depth=0` | Pass | Dependency tree complete. |
| `npm exec -- tsc -b` | Pass | No TypeScript errors. |
| `npm run build` | Pass | Vite transformed 1,773 modules; JS 227.78 kB, CSS 9.78 kB. |

There is no pytest configuration/dependency, no unit-test directory, no frontend test script, no component tests, no Playwright/Cypress tests, and no production smoke test against deployed services. GitHub Actions itself was inspected but not remotely executed.

## J. Deployment readiness

### Vercel

Status: **blocked**.

- `frontend/vercel.json` provides a normal SPA rewrite and the Vite build itself passes.
- `VITE_API_URL` is documented and required.
- The checked-in lockfile resolves every package through an internal artifact gateway; `npm ci` failed. Vercel/GitHub-hosted builders should not be assumed to access this host.
- No browser PWA audit, install test, offline navigation test, or iOS safe-area/install test was performed.

### Render

Status: **not ready**.

- `render.yaml`, Dockerfile, health path, runtime, and required variables exist.
- `/health` does not test the database or storage.
- There are no migrations or release/pre-deploy migration command.
- Silent local image fallback will write to ephemeral Render storage.
- Startup performs database DDL immediately and has no retry/readiness handling.

### Supabase PostgreSQL and Storage

Status: **not tested and unsafe to assume ready**.

- No live Supabase connection or bucket was supplied.
- No SQL migrations, RLS design, storage policy, bucket validation, signed/private URL strategy, or integration tests exist.
- The backend uses the service-role key, so key protection and strict server-only use are mandatory.
- Storage failure is hidden by local fallback.

### Environment variables

Documented: `DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `VITE_API_URL`.

Blockers: production credential storage/rotation, a public-registry lockfile, a migration workflow, exact PostgreSQL driver URL, strict CORS origins, verified Supabase bucket policy, and prevention of local-storage fallback in production.

## K. Prioritized repair plan

The counts below define the terminal summary: **4 critical issues** and **8 high issues**.

### Critical (4)

1. Replace hardcoded plaintext accounts/codes with migrated user records, strong password/code hashing, unique initial credentials, rotation, throttling/lockout, and revocable server-validated sessions/tokens.
2. Make restore reject incomplete/unknown schemas, validate every required table/field before deletion, stage and verify data, keep DB/files/audit consistent, and add destructive restore tests. Disable restore in production until fixed.
3. Make every business mutation and its audit row one database transaction; remove or strictly constrain client-authored audit creation; cover every required edit/archive/restore/transfer/census/finance/herder action with old/new identity tests.
4. Regenerate `package-lock.json` with portable public registry URLs and prove the exact `.github/workflows/ci.yml`/Vercel `npm ci` path succeeds before deployment.

### High (8)

1. Fix horse living-status semantics so pregnancy and other non-archived states remain in lists/statistics; add status enums and boundary/order tests.
2. Correct sheep/goat census definitions and totals, enforce nonnegative values, define whether subcategories overlap, and add audited edit/correction APIs.
3. Enforce cattle invariants on create and update, add restore/history, expose image URLs, and build actual detail/edit/image UI.
4. Replace localStorage “sync” with a durable operation queue using idempotency keys, per-user ownership, retry classes, conflict resolution, file handling, and explicit pending/failed UI.
5. Store real dated inventory snapshots/events and implement January 1 growth history; render every required dashboard widget and checkbox state.
6. Make production storage fail closed, use safe path containment, define image privacy, retain needed detail-image metadata, and test Supabase upload/read/delete behavior.
7. Add Alembic migrations, database constraints, PostgreSQL integration tests, sequence repair after restore, and an explicit production migration/release step.
8. Complete required frontend workflows: horse edit/restore/history, cattle edit/restore/images, mortality, census/finance edits, herder management, audit old/new display, and backup restore confirmation/validation.

### Medium

- Add pytest/unit tests, API integration fixtures, frontend tests, browser/PWA tests, and deployed smoke tests.
- Dispose SQLAlchemy engines before smoke-script cleanup; configure `StaticPool` for in-memory SQLite tests.
- Improve XLSX/PDF reports with business labels, filters, archive/loss/herder coverage, and verified Mongolian font embedding.
- Add database/storage readiness checks, structured logging, error monitoring, request IDs, backup size/retention policy, and operational documentation.
- Pin dependency ranges in `package.json` rather than relying on `latest`, while retaining a portable lockfile.

### Low

- Remove “Phase” and “Production PWA” UI labels until release criteria are met.
- Split the dense one-file frontend and backend into testable feature modules after behavior is stabilized.
- Enable unused-code/lint checks and remove unused imports/props such as `isOwner`.
- Add accessible non-prompt dialogs and clearer error/pending states.

## L. Recommended next implementation phase

The smallest realistic next phase is a **security and data-integrity foundation**, not a redesign. Its exit criterion should be: portable CI passes; users are stored and hashed; migrations reproduce the schema; restore cannot delete data from an incomplete archive; and one representative create/update/archive/restore flow commits its audit row atomically.

Likely files to change:

- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/auth.py`
- `backend/app/audit.py`
- `backend/app/database.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- new `backend/alembic.ini`
- new `backend/migrations/` initial and auth/constraint migrations
- new backend pytest tests, especially auth/audit/restore/PostgreSQL integration tests
- `frontend/package.json`
- `frontend/package-lock.json`
- `.github/workflows/ci.yml`
- `render.yaml`

Do not start the full feature redesign until this foundation is green. Afterward, implement one audited vertical slice at a time, beginning with correct horse status/list/edit/restore behavior, then cattle, census, finance/herders, analytics snapshots, and finally durable offline sync.

---

## Terminal summary

- Overall status: **partially implemented**
- Critical issues: **4**
- High issues: **8**
- Safe to deploy: **No**
- Recommended next action: **fix authentication, restore validation, atomic audit transactions, portable npm/CI installation, and migrations before adding or redesigning features**

---

## M. Remediation update — 2026-07-15

This section supersedes the original point-in-time findings above. The original evidence is retained for traceability.

| Original finding | Remediation | Evidence / test reference |
|---|---|---|
| Plaintext hardcoded accounts and 30-day trusted-role JWT | **Fixed** | DB `User`/`UserSession`/`LoginAttempt`, Argon2id seed, short access tokens, rotating hashed refresh sessions; `test_auth_audit.py` |
| Incomplete `{}` restore wipes rows | **Fixed locally** | Exact manifest/table/column/checksum/identity/FK validation before deletion; valid and empty/malformed/traversal tests in backup test files |
| Audit separate commit/client fabrication | **Fixed** | Server-only add-without-commit audit and shared handler transaction; no POST audit; rollback/actor tests |
| Internal npm lock URLs / `npm ci` failure | **Fixed** | Public registry lockfile; clean `npm ci` executed successfully |
| No migrations/import-time `create_all` | **Fixed** | Alembic initial migration; app startup has no `create_all`; SQLite upgrade and drift check pass |
| In-memory SQLite missing tables / Windows cleanup | **Fixed** | `StaticPool`, foreign-key pragma, scoped sessions; pytest uses isolated DB lifecycle |
| Pregnant horses omitted | **Fixed** | Typed living statuses and pregnancy tree/statistics test |
| Negative census and omitted төлөг/борлон | **Fixed** | Pydantic/DB nonnegative constraints and non-overlapping totals; census test expects 67 |
| Female breeding bull accepted | **Fixed** | Full resulting-state validation on create/update and DB check; cattle patch test |
| Missing horse/cattle archive restore, transfer history, edit/images UI | **Fixed** | New Animals feature pages and corresponding API routes |
| Missing census correction, mortality, finance/herder management UI | **Fixed** | New Operations feature pages; authorization tests |
| Fake historical growth and incomplete charts/toggles | **Fixed** | Explicit January 1 snapshots, null unknown history, Recharts dashboard, persisted preferences |
| Unsafe localStorage offline queue / false success | **Fixed for approved creates** | IndexedDB queue, user ownership, idempotency, explicit statuses; auth/files excluded; frontend queue tests |
| Public local uploads / silent production fallback | **Fixed in code; live service not tested** | Authenticated signed image route and production fail-closed Supabase storage; spoof test |
| Minimal reports | **Partially fixed** | Multi-sheet Excel and readable PDF with filters in API; UI filter controls remain absent; file signature tests |
| Fake production readiness endpoint | **Fixed** | `/health` is liveness; `/ready` executes DB query and reads Alembic revision |
| Vercel/Render/Supabase readiness | **Partially fixed / not live-tested** | Portable build, Render pre-deploy migration, production validation, PostgreSQL CI service. Live platforms unavailable |
| Missing tests | **Partially fixed** | 25 backend and 4 frontend tests plus lint/typecheck/build. Playwright/device E2E remains missing |

### Updated terminal summary

- Overall status: **release candidate with external verification gates**
- Original critical issues fixed in locally tested code: **4 of 4**
- Known critical issues remaining locally: **0**
- High-risk unverified areas: **PostgreSQL runtime, live Supabase storage, browser/E2E/device behavior**
- Safe to deploy immediately: **No**
- Next action: **run the PostgreSQL CI job, then the staged deployment and device checklist**

## N. External verification update — 2026-07-16

- **PASS:** Git initialized on `main`; generated artifacts and secrets ignored; logical commits created.
- **PASS:** Backend regression after dependency upgrades — 31 passed, 2 external/dialect skips.
- **PASS:** Frontend lint, typecheck, 4 unit tests, and production build.
- **PASS:** Playwright — 16 passed, 2 intentional duplicate-mutation skips across desktop/iPhone-like/Android-like Chromium.
- **PASS:** Automated PWA shell offline reload, indicator, manifest, service-worker registration, and no API cache.
- **PASS:** npm production audit and final pip audit have no known vulnerabilities.
- **BLOCKED:** PostgreSQL. Local PostgreSQL 18 accepts connections but needs a SCRAM password not present in the environment; Docker Desktop engine is stopped.
- **BLOCKED:** Supabase Storage. Required environment variables are absent; live lifecycle test/workflow is ready.
- **NOT TESTED:** physical device installation and hosted Render/Vercel staging.

Final status remains **release candidate**. Critical locally verified findings: **0**. Safe to deploy: **No**.
