#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Calls `run_ingest` on the LOCAL emulator as an authenticated test user.
# Exit codes: 0 ok, 1 error, 2 restart of ./rundev.sh required (params are read at startup).
usage() { echo "Usage: ./ingest-local.sh [--reset-user] [--lookback N]"; }

RESET_USER=false
LOOKBACK=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset-user) RESET_USER=true; shift ;;
    --lookback)
      [[ "${2:-}" =~ ^[1-9][0-9]*$ ]] || { echo "--lookback needs a positive integer"; usage; exit 1; }
      LOOKBACK="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; exit 1 ;;
  esac
done

PY=functions/venv/bin/python
[[ -x "$PY" ]] || PY=python3
ENV_LOCAL=functions/.env.local
REGION=europe-west1
EMAIL="dave@test.local"
export TEST_USER_PASSWORD="${TEST_USER_PASSWORD:-local-only-test-password}"  # emulator only, not a secret
API_KEY=fake-api-key

# --- Config: emulator hosts/ports from firebase.json, project from .firebaserc -------------------
EMULATOR_CONFIG=$("$PY" -c '
import json, sys
cfg = json.load(open("firebase.json")).get("emulators", {})
local = {"", "localhost", "127.0.0.1", "::1"}
for name in ("auth", "functions", "ui"):
    host = cfg.get(name, {}).get("host", "")
    if host not in local:
        sys.exit(f"refusing non-local emulator host for {name}: {host}")
get = lambda n, d: cfg.get(n, {}).get("port", d)
print(get("auth", 9099), get("functions", 5001), get("ui", 4000))
')
read -r AUTH_PORT FUNCTIONS_PORT UI_PORT <<<"$EMULATOR_CONFIG"
[[ -n "${AUTH_PORT:-}" && -n "${FUNCTIONS_PORT:-}" && -n "${UI_PORT:-}" ]] || { echo "Could not read emulator config from firebase.json"; exit 1; }
PROJECT=$("$PY" -c 'import json; print(json.load(open(".firebaserc"))["projects"]["default"])')

AUTH_URL="http://127.0.0.1:$AUTH_PORT"
FUNCTIONS_URL="http://127.0.0.1:$FUNCTIONS_PORT"

is_listening() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }  # plain TCP check: no HTTP request noise
for pair in "Auth:$AUTH_PORT" "Functions:$FUNCTIONS_PORT"; do
  if ! is_listening "${pair#*:}"; then
    echo "The ${pair%%:*} emulator is not reachable at 127.0.0.1:${pair#*:}."
    echo "Start it in another terminal with: ./rundev.sh"
    exit 1
  fi
done

# --- Helpers (tokens are kept in shell variables and never printed) -------------------------------
json_get() { # json_get a.b.c  (JSON on stdin)
  "$PY" -c '
import json, sys
v = json.load(sys.stdin)
for k in sys.argv[1].split("."):
    v = v.get(k) if isinstance(v, dict) else None
print("" if v is None else v)' "$1"
}

auth_post() { # auth_post <endpoint> <json body on stdin>
  curl -s --max-time 10 -X POST -H 'Content-Type: application/json' --data @- \
    "$AUTH_URL/identitytoolkit.googleapis.com/v1/$1?key=$API_KEY"
}

credentials_body() {
  EMAIL="$EMAIL" "$PY" -c '
import json, os
print(json.dumps({"email": os.environ["EMAIL"], "password": os.environ["TEST_USER_PASSWORD"],
                  "returnSecureToken": True}))'
}

get_key() {
  local line
  line=$(grep -E "^[[:space:]]*$1=" "$2" 2>/dev/null | tail -n 1 || true)
  line=${line#*=}; line=${line%$'\r'}; line=${line#[\"\']}; line=${line%[\"\']}
  printf '%s' "$line"
}

set_env_local() { # set_env_local KEY VALUE: updates only that key, keeps other lines
  "$PY" - "$ENV_LOCAL" "$1" "$2" <<'PYEOF'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("gmail_auth", "scripts/gmail_auth.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.update_env_file(Path(sys.argv[1]), {sys.argv[2]: sys.argv[3]})
PYEOF
}

# --- Test user in the Auth emulator ---------------------------------------------------------------
sign_in() { credentials_body | auth_post accounts:signInWithPassword; }

response=$(sign_in)
if [[ "$RESET_USER" == true && -n "$(json_get idToken <<<"$response")" ]]; then
  "$PY" -c 'import json,sys; print(json.dumps({"idToken": json.load(sys.stdin)["idToken"]}))' \
    <<<"$response" | auth_post accounts:delete >/dev/null
  echo "Deleted test user $EMAIL"
  response=$(sign_in)
fi

if [[ -z "$(json_get idToken <<<"$response")" ]]; then
  case "$(json_get error.message <<<"$response")" in
    EMAIL_NOT_FOUND)
      response=$(credentials_body | auth_post accounts:signUp)
      echo "Created test user $EMAIL" ;;
    INVALID_PASSWORD*)
      echo "Test user exists with a different password: run ./ingest-local.sh --reset-user"
      exit 1 ;;
    *)
      echo "Auth emulator sign-in failed: $(json_get error.message <<<"$response")"
      exit 1 ;;
  esac
fi
ID_TOKEN=$(json_get idToken <<<"$response")
UID_LOCAL=$(json_get localId <<<"$response")
[[ -n "$ID_TOKEN" && -n "$UID_LOCAL" ]] || { echo "Could not obtain the test user credentials."; exit 1; }

# --- Align params in functions/.env.local (read by the emulator at startup) ------------------------
RESTART=false
if [[ "$(get_key ALLOWED_UID "$ENV_LOCAL")" != "$UID_LOCAL" ]]; then
  set_env_local ALLOWED_UID "$UID_LOCAL"
  echo "Updated ALLOWED_UID in $ENV_LOCAL (uid of $EMAIL)."
  RESTART=true
fi
if [[ -n "$LOOKBACK" && "$(get_key INGEST_LOOKBACK_DAYS "$ENV_LOCAL")" != "$LOOKBACK" ]]; then
  set_env_local INGEST_LOOKBACK_DAYS "$LOOKBACK"
  echo "Set INGEST_LOOKBACK_DAYS=$LOOKBACK in $ENV_LOCAL."
  RESTART=true
fi
if [[ "$RESTART" == true ]]; then
  echo "Restart ./rundev.sh (Ctrl+C, then run it again), then re-run ./ingest-local.sh."
  exit 2
fi

# --- Call run_ingest ---------------------------------------------------------------------------------
echo "Calling run_ingest on the emulator (project $PROJECT, $REGION)..."
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
status=$(curl -s --max-time 300 -o "$tmp" -w '%{http_code}' -X POST \
  -H "Authorization: Bearer $ID_TOKEN" -H 'Content-Type: application/json' -d '{"data":{}}' \
  "$FUNCTIONS_URL/$PROJECT/$REGION/run_ingest" || echo 000)

if [[ "$status" != 200 ]]; then
  echo "run_ingest failed (HTTP $status): $(json_get error.message <"$tmp" 2>/dev/null || true)"
  echo "See the ./rundev.sh terminal for details."
  echo "If it mentions invalid_grant, the Gmail token expired or was revoked: ./setup.sh --reauth"
  exit 1
fi

"$PY" - "$tmp" <<'PYEOF'
import json, sys
result = json.load(open(sys.argv[1])).get("result", {})
print("Summary:")
for key in ("listed", "created", "skipped", "unmatched", "errors"):
    print(f"  {key:<10}{result.get(key, '?')}")
PYEOF
echo
echo "Emails: http://127.0.0.1:$UI_PORT/firestore/default/data/emails"
