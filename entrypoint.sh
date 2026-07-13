#!/bin/sh
set -e

python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py createcachetable --database default 2>/dev/null || echo "cache table skipped"

echo "Seeding admin user and categories..."
python manage.py seed_data || echo "seed_data skipped (may already exist)"

exec gunicorn cladly.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --log-level info