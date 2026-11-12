#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
image_ref="${1:?Pass an immutable GHCR image digest}"
rollback=false
if [[ "$image_ref" == '--rollback' ]]; then
  test -f image.previous.env || { echo 'No previous image is available' >&2; exit 1; }
  image_ref="$(sed -n 's/^RENTAL_IMAGE=//p' image.previous.env)"
  rollback=true
fi
if [[ ! "$image_ref" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]; then
  echo "Invalid image digest" >&2
  exit 1
fi
test -f .env || { echo 'Create .env with DOMAIN before enabling deployment' >&2; exit 1; }
if [[ "$rollback" == false && -f image.env ]]; then cp image.env image.previous.env; fi
printf 'RENTAL_IMAGE=%s\n' "$image_ref" > image.env.tmp
mv image.env.tmp image.env
compose=(docker compose --env-file .env --env-file image.env -f compose.production.yml)
if "${compose[@]}" pull && "${compose[@]}" up -d --wait --wait-timeout 120; then
  printf '%s\n' "$image_ref" > deployed-image.txt
  echo 'Deployment passed container readiness checks.'
else
  echo 'Deployment failed; restoring the previous image.' >&2
  if [[ -f image.previous.env ]]; then
    cp image.previous.env image.env
    "${compose[@]}" up -d --wait --wait-timeout 120
  else
    "${compose[@]}" down
  fi
  exit 1
fi
