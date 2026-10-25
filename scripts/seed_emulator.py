"""Loads fixtures/emails/*.eml into `emails/` of the Firestore EMULATOR.

Refuses to run without FIRESTORE_EMULATOR_HOST, so it can never write to production.
Run from the repo root:
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 PYTHONPATH=functions \
      functions/venv/bin/python scripts/seed_emulator.py
"""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from google.cloud import firestore

from distillo.ingest.mime import parse_email
from distillo.ingest.service import build_email_doc

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "emails"
PROJECT_ID = "distillo-prod"


def main() -> int:
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        print("FIRESTORE_EMULATOR_HOST is not set: refusing to run.", file=sys.stderr)
        return 1

    files = sorted(FIXTURES.glob("*.eml"))
    if not files:
        print(f"No .eml files in {FIXTURES}")
        return 0

    db = firestore.Client(project=PROJECT_ID)

    def is_enabled(source_id: str) -> bool:
        snap = db.collection("sourceSettings").document(source_id).get()
        return snap.get("enabled") is not False if snap.exists else True

    for path in files:
        parsed = parse_email(path.read_bytes())
        doc = build_email_doc(parsed, parsed.date or datetime.now(UTC), is_enabled)
        db.collection("emails").document(path.stem).set(doc.to_firestore())
        print(f"{path.name}: {doc.status} (source={doc.source_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
