#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then python3.12 -m venv .venv; fi
lock_digest="$(sha256sum requirements.lock | cut -d ' ' -f 1)"
if [[ ! -f .venv/rental-lock.sha256 ]] || [[ "$(cat .venv/rental-lock.sha256)" != "$lock_digest" ]]; then
  .venv/bin/python -m pip install --require-hashes -r requirements.lock
  .venv/bin/python -m pip install --no-deps -e .
  printf '%s\n' "$lock_digest" > .venv/rental-lock.sha256
fi
if [[ "$(node -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || printf '0')" -ge 22 ]]; then
  (cd frontend && npm ci && npm run build)
else
  (cd frontend && npx --yes --package=node@22 -c 'npm ci && npm run build')
fi
if [[ ! -f artifacts/registry.json ]]; then .venv/bin/python -m hanoi_rentals.cli train; fi
printf '\nHanoi Rent Insight: http://127.0.0.1:%s\n' "${PORT:-8000}"
exec .venv/bin/python -m hanoi_rentals.cli serve --port "${PORT:-8000}"
