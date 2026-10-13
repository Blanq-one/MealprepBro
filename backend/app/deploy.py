"""The backend's Vercel build step (vercel.json -> services.api.buildCommand): `python -m app.deploy`.

Runs the database migrations before the new code goes live, on production deployments only, and only when
RUN_MIGRATIONS_ON_DEPLOY=1. Migrations are additive by policy (BUILD_PLAN §4.1: new tables, nullable columns,
indexes), so the code that is still live keeps working on the new schema while the deployment finishes.
Preview deployments never touch the database. Without the flag, run `python -m app.cli migrate` yourself
(docs/deploy.md). A production deployment whose settings are unsafe (app/production.py) fails here, before
anything goes live."""

import os
import sys

from app.cli import main as cli_main
from app.config import get_settings
from app.production import production_problems


def should_migrate(env: dict[str, str]) -> tuple[bool, str]:
    if env.get("RUN_MIGRATIONS_ON_DEPLOY") != "1":
        return False, "RUN_MIGRATIONS_ON_DEPLOY is not 1: skipping migrations"
    if env.get("VERCEL_ENV") != "production":
        return False, f"VERCEL_ENV is {env.get('VERCEL_ENV')!r}, not production: skipping migrations"
    if not (env.get("DATABASE_URL_UNPOOLED") or env.get("DATABASE_URL")):
        return False, "no DATABASE_URL_UNPOOLED or DATABASE_URL: skipping migrations"
    return True, "migrating the production database"


def main() -> int:
    # an unsafe production configuration stops the build before anything goes live (app/production.py)
    if problems := production_problems(get_settings()):
        print("app.deploy: refusing to deploy to production: " + "; ".join(problems), file=sys.stderr)
        return 1
    ok, why = should_migrate(dict(os.environ))
    print(f"app.deploy: {why}")
    return cli_main(["migrate"]) if ok else 0


if __name__ == "__main__":
    sys.exit(main())
