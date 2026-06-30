#!/bin/sh
# Apply Alembic migrations when RUN_MIGRATIONS=true (used by the dev `api`
# service, which has no separate migrate step), then exec the container command.
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
    alembic upgrade head
fi

exec "$@"
