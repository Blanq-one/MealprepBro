#!/usr/bin/env bash
# Fresh-clone Docker test check (CLAUDE.md build workflow): run at the end of every phase, even when
# dependencies didn't change.
#
# Clones the committed HEAD into a temp directory, builds the backend image from that clone alone, and runs
# the full test suite inside it against this repo's db-test container. Proves the committed files are enough
# (nothing depends on untracked local files or the local virtualenv). Cleans up the clone and the image.
#
# Usage (from anywhere in the repo, after committing):  scripts/fresh_clone_check.sh
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: don't rewrite the database URL

REPO="$(git rev-parse --show-toplevel)"
COMPOSE=(docker compose -f "$REPO/docker-compose.yml")
COMMIT="$(git -C "$REPO" rev-parse --short HEAD)"
IMAGE="mealbro-fresh-check:$COMMIT"
WORK="$(mktemp -d)"
trap 'docker rmi -f "$IMAGE" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

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

echo "== running the test suite in the fresh image"
docker run --rm --network "$NETWORK" \
  -e TEST_DATABASE_URL=postgresql+psycopg://mealbro:mealbro@db-test:5432/mealbro_test \
  "$IMAGE" uv run --frozen pytest -q -p no:cacheprovider
