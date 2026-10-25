#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

REAUTH=false
case "${1:-}" in
  "") ;;
  --reauth) REAUTH=true ;;
  *) echo "Usage: ./setup.sh [--reauth]"; exit 1 ;;
esac

SECRET_FILE=functions/.secret.local

PY="${PYTHON:-python3.13}"
command -v "$PY" >/dev/null || PY=python3
command -v firebase >/dev/null || echo "WARNING: firebase CLI missing (npm i -g firebase-tools)"

if [[ ! -d functions/venv ]]; then
  "$PY" -m venv functions/venv
  echo "created functions/venv ($("$PY" --version))"
fi
functions/venv/bin/pip install -q -r functions/requirements.txt -r functions/requirements-dev.txt

# Create the local files from the examples only if missing: never overwrites existing values.
for f in functions/.env.local "$SECRET_FILE"; do
  if [[ -f "$f" ]]; then
    echo "ok: $f already exists (left untouched)"
  else
    cp "$f.example" "$f"
    echo "created: $f"
  fi
done
chmod 600 "$SECRET_FILE"

# Prints the value of KEY in a dotenv file (last occurrence, optional quotes stripped).
get_key() {
  local line
  line=$(grep -E "^[[:space:]]*$1=" "$2" | tail -n 1 || true)
  line=${line#*=}
  line=${line%$'\r'}
  line=${line#[\"\']}
  line=${line%[\"\']}
  printf '%s' "$line"
}

# --- Gmail authorisation ---------------------------------------------------------------------
if [[ "$REAUTH" == true || -z "$(get_key GMAIL_REFRESH_TOKEN "$SECRET_FILE")" ]]; then
  client_id=$(get_key GMAIL_CLIENT_ID "$SECRET_FILE")
  client_secret=$(get_key GMAIL_CLIENT_SECRET "$SECRET_FILE")

  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    [[ -t 0 ]] || { echo "Gmail client credentials are needed: run ./setup.sh from a terminal."; exit 1; }
    echo "Gmail OAuth client of type 'Desktop app' (Google Cloud console > APIs & Services > Credentials)."
    [[ -n "$client_id" ]] || read -r -p "GMAIL_CLIENT_ID: " client_id
    [[ -n "$client_secret" ]] || { read -r -s -p "GMAIL_CLIENT_SECRET (hidden): " client_secret; echo; }
  else
    echo "Using GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET already present in $SECRET_FILE"
  fi

  if [[ -z "$client_id" || -z "$client_secret" ]]; then
    echo "Client ID and secret must not be empty."; exit 1
  fi

  echo "Starting the Gmail authorisation: a browser window will open."
  # Values are passed as environment of this single process only (not exported, not in argv).
  GMAIL_CLIENT_ID="$client_id" GMAIL_CLIENT_SECRET="$client_secret" \
    functions/venv/bin/python scripts/gmail_auth.py --write-secret-local
  unset client_id client_secret
else
  echo "Gmail already authorised, use --reauth to redo it"
fi

cat <<MSG

Next steps:

1. Allowed uid: put the Firebase Auth uid of the single allowed user in
   functions/.env, functions/.env.local and in allowedUid() of firestore.rules
   (replace REPLACE_WITH_UID; emulator uid: UI at http://127.0.0.1:4000 > Authentication).

2. Local run: ./rundev.sh

3. Production secrets (once; the firebase CLI prompts for each value, nothing is printed here):
   firebase functions:secrets:set GMAIL_CLIENT_ID --project distillo-prod
   firebase functions:secrets:set GMAIL_CLIENT_SECRET --project distillo-prod
   firebase functions:secrets:set GMAIL_REFRESH_TOKEN --project distillo-prod

4. Deploy: ./deploy.sh
MSG
