# Security Review

## Resolved critical findings

- Plaintext production accounts: replaced with DB users and Argon2id hashes; seed secrets are environment-only.
- Incomplete backup data wipe: exact schema, manifest, checksum, identity, and FK validation occurs before deletion; destructive regression tests pass.
- Non-atomic business/audit writes: audit functions only add rows; feature handlers commit business state and audit together.
- Arbitrary audit fabrication: general audit POST is removed; audit reads are owner-only.
- Portable dependency risk: lockfile now resolves through `https://registry.npmjs.org` and `npm ci` passes.

## Authentication/session threat model

Access tokens are short-lived and kept in sessionStorage because the frontend and API are separate origins. This remains readable by injected script, so XSS prevention is important. Refresh tokens are high-entropy, stored only as SHA-256 hashes server-side, rotated on use, and delivered in an HTTP-only Secure SameSite=None cookie in production. DB user/session/token-version checks run on every authenticated request. Logout revokes the session.

Login attempts are tracked by username and IP window, with bounded failure and lock periods. Responses do not distinguish absent, disabled, or wrong-code accounts. Successful/failed/blocked login activity is audited.

## Authorization

Owner and module dependencies protect business routes; workers cannot reach owner audit, finance, herder, reports, backups, analytics, mortality, or user administration. Frontend hiding is only presentation. The automated matrix covers representative routes for all four roles, and backup/report denial has explicit tests.

## Data and storage

Registration numbers remain owner-only and are masked in audit values. Backups contain sensitive values and hashes and must be encrypted by the storage/operations layer. Image objects are private and accessed through an authenticated signed endpoint. Production storage is mandatory and fail-closed.

## Remaining risk

- Live Supabase bucket policy, signed URL expiry, deletion lifecycle, and service-role isolation are NOT TESTED.
- PostgreSQL behavior and concurrency are NOT TESTED locally; CI is configured but was not executed here.
- CSP/security headers are not currently set by application infrastructure; configure them at Vercel/Render after compatibility testing.
- No MFA is implemented for the owner.
- Refresh cookies rely on exact CORS origins and browser third-party-cookie behavior; validate on target Safari/Chrome devices.
- Backups are not encrypted by the app.
- Cross-system DB/object restore cannot be one physical transaction; operations must retain the automatic pre-restore backup and monitor failures.

Known remaining critical findings in locally exercised code: **0**. Production approval still requires the external checks above.

## 2026-07-16 recheck

- PASS: production npm audit found zero vulnerabilities.
- PASS: final pip audit found no known vulnerabilities after upgrading PyJWT 2.13.0, python-multipart 0.0.31, Pillow 12.3.0, pytest 9.0.3, and FastAPI 0.139.0 with its fixed Starlette line.
- PASS: final source scan found no production plaintext codes, service-role keys, database credentials, internal npm registries, localStorage auth/queue, import-time production `create_all`, or client-authored audit endpoint. Required initial codes occur only in isolated test fixtures/E2E seed code and documentation.
- PASS: automated browser checks confirmed protected API denials and that service-worker caches contain no API URLs.
- BLOCKED: live Supabase policy/service-role isolation and PostgreSQL runtime behavior still require credentials.
- NOT TESTED: physical-device cross-site cookie behavior and installability.
