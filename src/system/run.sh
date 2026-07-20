#!/usr/bin/env bash
set -euo pipefail

SYSTEM_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SYSTEM_DIR/../.." && pwd)"

if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi

if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
fi

source "$PROJECT_ROOT/.venv/bin/activate"
cd "$SYSTEM_DIR"
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_initial_data
python manage.py check
python manage.py runserver 127.0.0.1:8000
