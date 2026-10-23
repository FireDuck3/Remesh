#!/usr/bin/env bash
# Render build step: install, collect static files, migrate, make sure the manager role and (once) the catalog exist.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py setup_roles
python manage.py seed_remesh --if-empty
