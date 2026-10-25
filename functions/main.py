from distillo.config import (  # isort: skip  (config must be imported before any function is defined)
    ALLOWED_UID,
    GMAIL_CLIENT_ID,
    GMAIL_CLIENT_SECRET,
    GMAIL_REFRESH_TOKEN,
    GMAIL_SECRETS,
    INGEST_LOOKBACK_DAYS,
    INGEST_MAX_MESSAGES,
    INGEST_SCHEDULE,
)

import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn, logger, options, scheduler_fn

from distillo.ingest.gmail import build_gmail_service
from distillo.ingest.service import IngestSummary, ingest

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()


def _run_ingest() -> IngestSummary:
    # Params and secrets are read at runtime only, never at import time.
    gmail = build_gmail_service(
        GMAIL_CLIENT_ID.value, GMAIL_CLIENT_SECRET.value, GMAIL_REFRESH_TOKEN.value
    )
    return ingest(
        gmail=gmail,
        db=firestore.client(),
        lookback_days=INGEST_LOOKBACK_DAYS.value,
        max_messages=INGEST_MAX_MESSAGES.value,
    )


@scheduler_fn.on_schedule(
    schedule=INGEST_SCHEDULE,
    timezone=options.Timezone("Europe/Rome"),
    secrets=GMAIL_SECRETS,
    timeout_sec=300,
)
def ingest_scheduled(event: scheduler_fn.ScheduledEvent) -> None:
    _run_ingest()


@https_fn.on_call(secrets=GMAIL_SECRETS, timeout_sec=300)
def run_ingest(req: https_fn.CallableRequest[object]) -> IngestSummary:
    if req.auth is None or req.auth.uid != ALLOWED_UID.value:
        logger.warn("run_ingest rejected", authenticated=req.auth is not None)
        raise https_fn.HttpsError(https_fn.FunctionsErrorCode.PERMISSION_DENIED, "Not allowed")
    return _run_ingest()
