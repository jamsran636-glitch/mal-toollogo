param(
  [string]$TestDatabaseUrl = $env:POSTGRES_TEST_URL
)

$ErrorActionPreference = "Stop"
if (-not $TestDatabaseUrl) {
  throw "Set POSTGRES_TEST_URL to a clean disposable PostgreSQL database."
}
if ($TestDatabaseUrl -notmatch '^postgres(?:ql)?(\+psycopg)?://' -or $TestDatabaseUrl -notmatch '(mal_test|integration|_test)') {
  throw "Refusing to run: URL must be PostgreSQL and database name must contain mal_test, integration, or _test."
}

$env:APP_ENV = "test"
$env:DATABASE_URL = $TestDatabaseUrl
$env:JWT_SECRET = "postgres-verification-only-secret-at-least-32-characters"

Push-Location (Join-Path $PSScriptRoot "..\backend")
try {
  uv run --python 3.12 --with-requirements requirements.txt alembic upgrade head
  uv run --python 3.12 --with-requirements requirements.txt alembic current
  uv run --python 3.12 --with-requirements requirements.txt alembic check
  uv run --python 3.12 --with-requirements requirements.txt pytest -q
} finally {
  Pop-Location
}
