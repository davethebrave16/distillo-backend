"""One-off: obtains a Gmail refresh token (gmail.readonly) through the local OAuth flow.

Run from the repo root:
    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... \
      functions/venv/bin/python scripts/gmail_auth.py

The token is printed to the terminal only, never written to a file.
"""

import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main() -> int:
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET (OAuth client of type 'Desktop app').",
            file=sys.stderr,
        )
        return 1

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    # prompt=consent forces a refresh token even if access was already granted
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    if not credentials.refresh_token:
        print("No refresh token returned. Revoke the app's access and retry.", file=sys.stderr)
        return 1

    print("\nRefresh token (shown once, not saved anywhere):\n")
    print(credentials.refresh_token)
    print("\nStore the secrets (each command prompts for the value):\n")
    for name in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        print(f"  firebase functions:secrets:set {name} --project distillo-prod")
    return 0


if __name__ == "__main__":
    sys.exit(main())
