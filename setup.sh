#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3.13}"
command -v "$PY" >/dev/null || PY=python3
command -v firebase >/dev/null || echo "WARNING: firebase CLI missing (npm i -g firebase-tools)"

if [[ ! -d functions/venv ]]; then
  "$PY" -m venv functions/venv
  echo "created functions/venv ($("$PY" --version))"
fi
functions/venv/bin/pip install -q -r functions/requirements.txt -r functions/requirements-dev.txt

# Create the local files from the examples only if missing: never overwrites existing values.
for f in functions/.env.local functions/.secret.local; do
  if [[ -f "$f" ]]; then
    echo "ok: $f already exists (left untouched)"
  else
    cp "$f.example" "$f"
    chmod 600 "$f"
    echo "created: $f"
  fi
done

cat <<MSG

To fill in by hand (never paste secrets in chat or commit them):

1. functions/.secret.local   (emulator secrets)
   GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET: OAuth client of type "Desktop app"
     (Google Cloud console > APIs & Services > Credentials)
   GMAIL_REFRESH_TOKEN: get it with
     GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... functions/venv/bin/python scripts/gmail_auth.py

2. functions/.env.local and functions/.env
   ALLOWED_UID: Firebase Auth uid of the single allowed user
     (emulator: UI at http://127.0.0.1:4000 > Authentication; production: Firebase console)

3. firestore.rules
   replace REPLACE_WITH_UID in allowedUid() with the same uid

4. Production secrets (once; each command prompts for the value):
   firebase functions:secrets:set GMAIL_CLIENT_ID --project distillo-prod
   firebase functions:secrets:set GMAIL_CLIENT_SECRET --project distillo-prod
   firebase functions:secrets:set GMAIL_REFRESH_TOKEN --project distillo-prod

Then run: ./rundev.sh
MSG
