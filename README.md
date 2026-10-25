# distillo-backend

Python backend (Firebase Functions 2nd gen, region `europe-west1`) of Distillo: ingests newsletters
from Gmail (label `news`) into Firestore. Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md);
master document: `../docs/ARCHITECTURE.md`. Roadmap steps 0–1 are implemented.

## Prerequisites
- Python 3.13 (minimum 3.12) with `venv`. Node is only needed for the Firebase CLI: `npm i -g firebase-tools`.
- Firebase project `distillo-prod` (Blaze), Firestore `(default)` in `europe-west1`.
- Gmail OAuth client of type *Desktop app*, Google Auth Platform published "In production".

## Setup
```bash
./setup.sh            # safe to re-run
./setup.sh --reauth   # redo the Gmail authorisation
```
`setup.sh`:
1. creates `functions/venv` and installs the dependencies;
2. creates `functions/.env.local` and `functions/.secret.local` from the `.example` files **only if missing**
   (never overwrites) and sets `.secret.local` to mode 600;
3. handles the **Gmail authorisation** when `GMAIL_REFRESH_TOKEN` is missing/empty in `.secret.local` (or with `--reauth`):
   it reuses `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` from `.secret.local` if present, otherwise asks for them
   (the secret is read hidden), opens the browser and writes the three `GMAIL_*` values into `functions/.secret.local`.
   Secrets are passed only as environment of the auth process, and are never printed or stored in versioned files;
4. prints the next steps.

Steps to finish by hand:

1. **Production secrets** (once; the firebase CLI prompts for each value):
   ```bash
   firebase functions:secrets:set GMAIL_CLIENT_ID --project distillo-prod
   firebase functions:secrets:set GMAIL_CLIENT_SECRET --project distillo-prod
   firebase functions:secrets:set GMAIL_REFRESH_TOKEN --project distillo-prod
   ```
2. **Gmail without `setup.sh`** (token printed instead of saved):
   `GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... functions/venv/bin/python scripts/gmail_auth.py`
3. **Allowed uid**: sign in once with Google (Auth emulator or production) and copy the uid.
   Replace `REPLACE_WITH_UID` in `firestore.rules` (function `allowedUid()`), in `functions/.env`
   and in `functions/.env.local`.

## Local quickstart
1. `./setup.sh`: venv, local config files, Gmail authorisation.
2. `./rundev.sh` (terminal A): starts the Auth, Firestore and Functions emulators (UI at http://127.0.0.1:4000).
3. `./ingest-local.sh` (terminal B): signs in (or creates) the test user `dave@test.local` in the Auth emulator and
   calls `run_ingest`. **The first run only aligns `ALLOWED_UID` in `functions/.env.local` with the test user's uid
   and exits with code 2**: restart `./rundev.sh` (params are read at startup) and run it again.
4. Open the `emails` collection in the Emulator UI (the script prints the URL): http://127.0.0.1:4000/firestore/default/data/emails

Options of `ingest-local.sh`:
- `--reset-user`: delete and recreate the test user in the Auth emulator.
- `--lookback N`: set `INGEST_LOOKBACK_DAYS=N` in `functions/.env.local` (e.g. for a backfill); needs a restart of `./rundev.sh`, so it exits with code 2.
- `TEST_USER_PASSWORD` env var overrides the fixed local-only test password.

Exit codes: `0` ok · `1` error (emulator unreachable, sign-in or call failed) · `2` restart `./rundev.sh`, then re-run.

The script only talks to `127.0.0.1` (hosts/ports from `firebase.json`, project from `.firebaserc`) and never prints tokens.
If the call fails with `invalid_grant` (visible in the `./rundev.sh` terminal), the Gmail token is expired or revoked: run `./setup.sh --reauth`.

## Environment variables (`functions/.env`, `functions/.env.local`)
| Name | Default | Meaning |
|---|---|---|
| `ALLOWED_UID` | – | uid allowed to call `run_ingest` |
| `INGEST_LOOKBACK_DAYS` | 3 | Gmail window (`newer_than:Nd`); raise it for a backfill |
| `INGEST_MAX_MESSAGES` | 50 | max messages per run |

Secrets: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.

## Usage
- `./setup.sh [--reauth]`: see Setup.
- `./ingest-local.sh [--reset-user] [--lookback N]`: see Local quickstart.
- `./rundev.sh [--seed]`: Auth/Firestore/Functions emulators (UI at http://127.0.0.1:4000);
  `--seed` loads `fixtures/emails/*.eml`. The schedule does not fire in the emulator: call `run_ingest`
  (callable, needs an authenticated user with the allowed uid).
- `./deploy.sh [all|functions|rules]`: ruff, mypy, pytest, then `firebase deploy` (project `default`, or `PROJECT=...`).
- Checks, from `functions/`: `venv/bin/ruff check .`, `venv/bin/ruff format --check .`,
  `venv/bin/mypy distillo main.py`, `venv/bin/pytest`.

A mail that ends up with `status: 'error'` is not retried: delete its document in `emails/` to retry it.
