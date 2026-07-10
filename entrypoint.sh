#!/bin/sh
set -e

python manage.py collectstatic --noinput
python manage.py migrate --noinput

exec gunicorn cladly.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --log-level info