#!/usr/bin/env bash
# Fresh-clone Docker test check (CLAUDE.md build workflow): run at the end of every phase, even when
# dependencies didn't change.
#
# Clones the committed HEAD into a temp directory, builds the backend image from that clone alone, and runs
# the full test suite inside it against this repo's db-test container (slow tests included; in parallel, each
# worker with its own database beside db-test's: backend/conftest.py); then builds the frontend image from the
# clone and runs its type check, its tests and the production build (the static export) inside it. Proves the
# committed files are enough (nothing depends on untracked local files, the local virtualenv or node_modules).
# Cleans up the clone and the images.
#
# Usage (from anywhere in the repo, after committing):  scripts/fresh_clone_check.sh [--workers N]
#   --workers N  at most N parallel test workers (pytest-xdist and Vitest), for a machine short on memory (AD4:
#                a run with one worker per CPU was stopped for low memory); default: one per CPU
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: don't rewrite the database URL

WORKERS=""
GIVEN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workers) GIVEN=1; WORKERS="${2:-}"; shift; [[ $# -gt 0 ]] && shift ;;
    --workers=*) GIVEN=1; WORKERS="${1#*=}"; shift ;;
    *) echo "unknown option: $1 (usage: scripts/fresh_clone_check.sh [--workers N])" >&2; exit 2 ;;
  esac
done
if [[ "$GIVEN" == 1 && ! "$WORKERS" =~ ^[1-9][0-9]*$ ]]; then
  echo "--workers takes a whole number above 0" >&2
  exit 2
fi
PYTEST_WORKERS=()
VITEST_WORKERS=""
if [[ -n "$WORKERS" ]]; then
  PYTEST_WORKERS=(-n "$WORKERS")
  VITEST_WORKERS="-- --maxWorkers=$WORKERS"
fi

REPO="$(git rev-parse --show-toplevel)"
COMPOSE=(docker compose -f "$REPO/docker-compose.yml")
COMMIT="$(git -C "$REPO" rev-parse --short HEAD)"
IMAGE="mealbro-fresh-check:$COMMIT"
WEB_IMAGE="mealbro-fresh-check-web:$COMMIT"
WORK="$(mktemp -d)"
trap 'docker rmi -f "$IMAGE" "$WEB_IMAGE" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

if [[ -n "$(git -C "$REPO" status --porcelain --untracked-files=no)" ]]; then
  echo "note: uncommitted changes are NOT part of this check (it tests commit $COMMIT)" >&2
fi

echo "== cloning $COMMIT"
git clone --quiet "$REPO" "$WORK/clone"

echo "== starting db-test (this repo's compose)"
"${COMPOSE[@]}" up -d --wait db-test >/dev/null

echo "== building the backend image from the clone"
docker build --quiet -t "$IMAGE" "$WORK/clone/backend" >/dev/null

NETWORK="$(docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}' \
  "$("${COMPOSE[@]}" ps -q db-test)")"

echo "== running the test suite in the fresh image (every test, slow ones included, in parallel: ${WORKERS:-one per CPU} workers)"
docker run --rm --network "$NETWORK" \
  -e TEST_DATABASE_URL=postgresql+psycopg://mealbro:mealbro@db-test:5432/mealbro_test \
  "$IMAGE" uv run --frozen pytest -q -p no:cacheprovider --run-slow "${PYTEST_WORKERS[@]}"

echo "== building the frontend image from the clone"
docker build --quiet -t "$WEB_IMAGE" "$WORK/clone/frontend" >/dev/null

echo "== frontend: type check, tests, production build"
docker run --rm "$WEB_IMAGE" sh -c "npm run typecheck && npm test $VITEST_WORKERS && npm run build"
