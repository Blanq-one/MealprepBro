#!/usr/bin/env bash
# Dev-server compile check (the 2b.6 approval, item 8): part of every step's end-of-step checks, beside the tests
# and the fresh-clone check. The dev frontend (next dev in this repo's compose, on a Windows bind mount) can keep
# serving a stale module graph after new files are added ("Module not found: Can't resolve
# '@/components/cook/TierCards'") until the container restarts, while the tests and the static export pass.
#
# Restarts this repo's frontend container (only it), waits for the dev server, then loads every page route
# (src/app/**/page.tsx) and fails when a page doesn't answer 200, or when the page or the dev server's log since
# the restart shows a compile error.
#
# Usage (from anywhere in the repo, with this repo's compose up):  scripts/dev_compile_check.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1

REPO="$(git rev-parse --show-toplevel)"
COMPOSE=(docker compose -f "$REPO/docker-compose.yml")
BASE="${DEV_URL:-http://localhost:3000}"
ERRORS='Module not found|Failed to compile|Build Error|Unhandled Runtime Error|SyntaxError'

echo "== restarting this repo's frontend container"
since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
"${COMPOSE[@]}" restart frontend >/dev/null

echo "== waiting for the dev server at $BASE"
for _ in $(seq 1 90); do
  if curl -fs -o /dev/null "$BASE/login/"; then break; fi
  sleep 2
done

failed=0
while IFS= read -r page; do
  route="${page#"$REPO/frontend/src/app"}"
  route="${route%page.tsx}"
  url="$BASE${route}"
  body="$(mktemp)"
  code="$(curl -s -o "$body" -w '%{http_code}' --max-time 120 "$url" || echo 000)"
  if [[ "$code" != "200" ]] || grep -Eq "$ERRORS" "$body"; then
    echo "FAIL $code $route"
    grep -Eo "($ERRORS)[^<]{0,160}" "$body" | head -3 || true
    failed=1
  else
    echo "ok   $code $route"
  fi
  rm -f "$body"
done < <(find "$REPO/frontend/src/app" -name page.tsx | sort)

if "${COMPOSE[@]}" logs frontend --since "$since" 2>&1 | grep -E "$ERRORS"; then
  echo "FAIL: the dev server's log shows a compile error since the restart"
  failed=1
fi

if [[ "$failed" != "0" ]]; then
  echo "== dev-server compile check FAILED"
  exit 1
fi
echo "== dev-server compile check passed: every page compiles and answers 200"
