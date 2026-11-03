#!/usr/bin/env bash
set -e

# Wait for PostgreSQL if DB_HOST is specified
if [ -n "$DB_HOST" ]; then
  echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT:-5432}..."
  while ! nc -z "$DB_HOST" "${DB_PORT:-5432}"; do
    sleep 0.5
  done
  echo "PostgreSQL is reachable."
fi

# Run database schema migrations
if [ "$RUN_MIGRATIONS" = "true" ] || [ "$1" = "daphne" ]; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput
fi

# Collect static assets if in production
if [ "$COLLECT_STATIC" = "true" ]; then
  echo "Collecting static assets..."
  python manage.py collectstatic --noinput --clear || true
fi

exec "$@"
