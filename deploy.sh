#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PROJECT="${PROJECT:-default}"          # alias in .firebaserc
TARGET="${1:-all}"                      # all | functions | rules
PY="${PYTHON:-python3}"

if [[ ! -d functions/venv ]]; then
  "$PY" -m venv functions/venv
fi
functions/venv/bin/pip install -q -r functions/requirements.txt -r functions/requirements-dev.txt

(
  cd functions
  venv/bin/ruff check .
  venv/bin/ruff format --check .
  venv/bin/mypy distillo main.py
  venv/bin/pytest -q
)

case "$TARGET" in
  functions) ONLY="functions" ;;
  rules)     ONLY="firestore:rules,firestore:indexes" ;;
  all)       ONLY="functions,firestore:rules,firestore:indexes" ;;
  *) echo "Usage: ./deploy.sh [all|functions|rules]"; exit 1 ;;
esac

firebase deploy --project "$PROJECT" --only "$ONLY"
