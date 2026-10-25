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
./setup.sh
```
Creates `functions/venv`, installs the dependencies and creates `functions/.env.local` and
`functions/.secret.local` from the `.example` files **only if they are missing** (it never overwrites).
It then prints what you still have to fill in. The `.example` files say where each value comes from.

1. **Gmail refresh token** (scope `gmail.readonly`):
   ```bash
   GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... functions/venv/bin/python scripts/gmail_auth.py
   ```
   The token is printed to the terminal only. Then, one at a time (each prompts for the value):
   ```bash
   firebase functions:secrets:set GMAIL_CLIENT_ID --project distillo-prod
   firebase functions:secrets:set GMAIL_CLIENT_SECRET --project distillo-prod
   firebase functions:secrets:set GMAIL_REFRESH_TOKEN --project distillo-prod
   ```
2. **Emulator**: fill in `functions/.secret.local` (GMAIL_*) and `functions/.env.local` (gitignored, created by `setup.sh`).
3. **Allowed uid**: sign in once with Google (Auth emulator or production) and copy the uid.
   Replace `REPLACE_WITH_UID` in `firestore.rules` (function `allowedUid()`), in `functions/.env`
   and in `functions/.env.local`.

## Environment variables (`functions/.env`, `functions/.env.local`)
| Name | Default | Meaning |
|---|---|---|
| `ALLOWED_UID` | – | uid allowed to call `run_ingest` |
| `INGEST_LOOKBACK_DAYS` | 3 | Gmail window (`newer_than:Nd`); raise it for a backfill |
| `INGEST_MAX_MESSAGES` | 50 | max messages per run |

Secrets: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`.

## Usage
- `./rundev.sh [--seed]`: Auth/Firestore/Functions emulators (UI at http://127.0.0.1:4000);
  `--seed` loads `fixtures/emails/*.eml`. The schedule does not fire in the emulator: call `run_ingest`
  (callable, needs an authenticated user with the allowed uid).
- `./deploy.sh [all|functions|rules]`: ruff, mypy, pytest, then `firebase deploy` (project `default`, or `PROJECT=...`).
- Checks, from `functions/`: `venv/bin/ruff check .`, `venv/bin/ruff format --check .`,
  `venv/bin/mypy distillo main.py`, `venv/bin/pytest`.

A mail that ends up with `status: 'error'` is not retried: delete its document in `emails/` to retry it.
