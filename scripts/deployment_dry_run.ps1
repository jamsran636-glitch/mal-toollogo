$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

Push-Location (Join-Path $root "backend")
try {
  uv run --python 3.12 --with-requirements requirements.txt python -m compileall -q app migrations tests
  uv run --python 3.12 --with-requirements requirements.txt ruff check app migrations tests
  uv run --python 3.12 --with-requirements requirements.txt ruff format --check app migrations tests
} finally { Pop-Location }

Push-Location (Join-Path $root "frontend")
try {
  npm ci --no-audit --no-fund
  npm run lint
  npm run typecheck
  npm test
  npm run build
} finally { Pop-Location }

$lock = Get-Content (Join-Path $root "frontend\package-lock.json") -Raw
if ($lock -match 'applied-caas|artifactory') { throw "Private registry URL found in lockfile." }
$manifest = Get-Content (Join-Path $root "frontend\public\manifest.webmanifest") -Raw | ConvertFrom-Json
if ($manifest.display -ne "standalone" -or $manifest.icons.Count -lt 2) { throw "PWA manifest validation failed." }
Write-Host "Deployment dry-run checks passed. External PostgreSQL, Supabase, and hosting checks remain separate gates."
