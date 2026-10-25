#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

command -v firebase >/dev/null || { echo "firebase CLI missing (npm i -g firebase-tools)"; exit 1; }
PY="${PYTHON:-python3}"

if [[ ! -d functions/venv ]]; then
  "$PY" -m venv functions/venv
fi
functions/venv/bin/pip install -q -r functions/requirements.txt -r functions/requirements-dev.txt

# optional: ./rundev.sh --seed loads the fixtures after the emulator starts
if [[ "${1:-}" == "--seed" ]]; then
  ( sleep 20 && FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 PYTHONPATH=functions \
      functions/venv/bin/python scripts/seed_emulator.py ) &
fi

firebase emulators:start \
  --only auth,firestore,functions \
  --import ./.emulator-data \
  --export-on-exit ./.emulator-data
