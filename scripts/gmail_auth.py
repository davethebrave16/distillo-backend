"""One-off: obtains a Gmail refresh token (gmail.readonly) through the local OAuth flow.

Run from the repo root (normally done by ./setup.sh):
    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... \
      functions/venv/bin/python scripts/gmail_auth.py [--write-secret-local]

Without the flag the refresh token is printed to the terminal only. With --write-secret-local
the three GMAIL_* values are written to functions/.secret.local (mode 600) and nothing secret
is printed. Secrets are read from the environment, never from command-line arguments.
"""

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRET_LOCAL = Path(__file__).resolve().parent.parent / "functions" / ".secret.local"


def update_env_file(path: Path, values: dict[str, str]) -> None:
    """Sets only the given KEY=value pairs in a dotenv file, preserving every other line.

    Creates the file if missing; writes atomically and leaves it with mode 600.
    """
    lines = path.read_text().splitlines() if path.exists() else []
    pending = dict(values)
    result: list[str] = []
    for line in lines:
        match = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        key = match.group(1) if match else None
        if key in values:
            if key in pending:  # first occurrence is replaced, duplicates are dropped
                result.append(f"{key}={pending.pop(key)}")
            continue
        result.append(line)
    result.extend(f"{key}={value}" for key, value in pending.items())

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write("\n".join(result) + "\n")
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Obtain a Gmail refresh token (gmail.readonly).")
    parser.add_argument(
        "--write-secret-local",
        action="store_true",
        help="write GMAIL_* into functions/.secret.local instead of printing the token",
    )
    args = parser.parse_args()

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

    if args.write_secret_local:
        update_env_file(
            SECRET_LOCAL,
            {
                "GMAIL_CLIENT_ID": client_id,
                "GMAIL_CLIENT_SECRET": client_secret,
                "GMAIL_REFRESH_TOKEN": credentials.refresh_token,
            },
        )
        print(f"Gmail authorised: GMAIL_* written to functions/{SECRET_LOCAL.name}.")
        return 0

    print("\nRefresh token (shown once, not saved anywhere):\n")
    print(credentials.refresh_token)
    print("\nStore the secrets (each command prompts for the value):\n")
    for name in ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        print(f"  firebase functions:secrets:set {name} --project distillo-prod")
    return 0


if __name__ == "__main__":
    sys.exit(main())
