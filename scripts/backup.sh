#!/usr/bin/env bash
# Back up the cloud database (Neon) to a local file with pg_dump, and restore it (docs/deploy.md).
#
#   scripts/backup.sh                      dump $DATABASE_URL_UNPOOLED to backups/mealbro-<UTC time>.dump
#   scripts/backup.sh restore FILE URL     restore a dump into the database at URL (an empty one, for a test)
#
# Uses the direct (unpooled) connection string: pg_dump needs a session, which Neon's pooler doesn't give.
# Runs pg_dump from the postgres:17 Docker image, so nothing has to be installed; a local pg_dump 17 is used
# if there is one. Neon Free also keeps 6 hours of history you can restore from in its console.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows: don't rewrite the URL or paths

REPO="$(git rev-parse --show-toplevel)"
OUT_DIR="$REPO/backups"  # gitignored

if [[ "${1:-}" == "restore" ]]; then
  file="${2:?usage: scripts/backup.sh restore FILE URL}"
  url="${3:?usage: scripts/backup.sh restore FILE URL}"
  name="$(basename "$file")"
  mkdir -p "$OUT_DIR"
  [[ -f "$OUT_DIR/$name" ]] || cp "$file" "$OUT_DIR/$name"
  if command -v pg_restore >/dev/null 2>&1 && pg_restore --version | grep -q " 17"; then
    pg_restore --no-owner --no-privileges --dbname "$url" "$OUT_DIR/$name"
  else
    docker run --rm -v "$OUT_DIR:/backups" postgres:17 \
      pg_restore --no-owner --no-privileges --dbname "$url" "/backups/$name"
  fi
  echo "restored $name"
  exit 0
fi

url="${DATABASE_URL_UNPOOLED:?set DATABASE_URL_UNPOOLED to the direct Neon connection string}"
url="${url/postgresql+psycopg:/postgresql:}"
mkdir -p "$OUT_DIR"
name="mealbro-$(date -u +%Y%m%dT%H%M%SZ).dump"
if command -v pg_dump >/dev/null 2>&1 && pg_dump --version | grep -q " 17"; then
  pg_dump --format=custom --no-owner --no-privileges --file "$OUT_DIR/$name" "$url"
else
  docker run --rm -v "$OUT_DIR:/backups" postgres:17 \
    pg_dump --format=custom --no-owner --no-privileges --file "/backups/$name" "$url"
fi
echo "wrote backups/$name ($(du -h "$OUT_DIR/$name" | cut -f1))"
