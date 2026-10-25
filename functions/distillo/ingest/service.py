from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypedDict

from firebase_functions import logger
from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from distillo.ingest.gmail import get_raw_message, list_message_ids
from distillo.ingest.html_to_md import html_to_markdown, plain_text_to_markdown
from distillo.ingest.mime import ParsedEmail, parse_email
from distillo.models import EmailDoc
from distillo.sources.registry import match_source

# Firestore documents are capped at 1 MiB.
MAX_MARKDOWN_CHARS = 400_000
_EXISTS_BATCH = 100
_ERROR_MAX_CHARS = 500


class IngestSummary(TypedDict):
    listed: int
    created: int
    skipped: int
    unmatched: int
    errors: int


def build_email_doc(
    parsed: ParsedEmail,
    received_at: datetime,
    is_source_enabled: Callable[[str], bool],
) -> EmailDoc:
    """Maps a parsed mail to its `emails/` document (status pending | unmatched | skipped).

    Raises ValueError if an enabled source's mail has no usable body.
    """
    base = {
        "from_address": parsed.from_header,
        "subject": parsed.subject,
        "received_at": received_at,
    }

    source = match_source(parsed.from_header)
    if source is None:
        return EmailDoc(source_id=None, markdown="", status="unmatched", **base)
    if not is_source_enabled(source.id):
        return EmailDoc(source_id=source.id, markdown="", status="skipped", **base)

    markdown = (
        html_to_markdown(parsed.body) if parsed.is_html else plain_text_to_markdown(parsed.body)
    )
    if not markdown:
        raise ValueError("message has no usable text/html or text/plain body")
    return EmailDoc(
        source_id=source.id, markdown=markdown[:MAX_MARKDOWN_CHARS], status="pending", **base
    )


def _existing_ids(db: firestore.Client, ids: list[str]) -> set[str]:
    existing: set[str] = set()
    for start in range(0, len(ids), _EXISTS_BATCH):
        refs = [db.collection("emails").document(i) for i in ids[start : start + _EXISTS_BATCH]]
        existing.update(
            snap.id for snap in db.get_all(refs, field_paths=["__name__"]) if snap.exists
        )
    return existing


def _make_enabled_checker(db: firestore.Client) -> Callable[[str], bool]:
    cache: dict[str, bool] = {}

    def is_enabled(source_id: str) -> bool:
        if source_id not in cache:
            snap = db.collection("sourceSettings").document(source_id).get()
            cache[source_id] = snap.get("enabled") is not False if snap.exists else True
        return cache[source_id]

    return is_enabled


def _record_error(db: firestore.Client, message_id: str, error: Exception) -> None:
    doc = EmailDoc(
        source_id=None,
        from_address="",
        subject="",
        received_at=datetime.now(UTC),
        markdown="",
        status="error",
        error=f"{type(error).__name__}: {error}"[:_ERROR_MAX_CHARS],
    )
    try:
        db.collection("emails").document(message_id).create(doc.to_firestore())
    except AlreadyExists:
        pass
    except Exception as write_error:
        logger.error("error doc write failed", messageId=message_id, error=str(write_error))


def ingest(
    *,
    gmail: Any,
    db: firestore.Client,
    lookback_days: int,
    max_messages: int,
) -> IngestSummary:
    """Gmail label `news` → `emails/{gmailMessageId}`. One failing mail never stops the run."""
    summary = IngestSummary(listed=0, created=0, skipped=0, unmatched=0, errors=0)

    ids = list_message_ids(gmail, f"label:news newer_than:{lookback_days}d", max_messages)
    summary["listed"] = len(ids)

    existing = _existing_ids(db, ids)
    is_enabled = _make_enabled_checker(db)

    for message_id in ids:
        if message_id in existing:
            continue
        try:
            parsed = parse_email(get_raw_message(gmail, message_id))
            doc = build_email_doc(parsed, parsed.date or datetime.now(UTC), is_enabled)
            db.collection("emails").document(message_id).create(doc.to_firestore())
        except AlreadyExists:
            continue  # a concurrent run won the race
        except Exception as error:
            summary["errors"] += 1
            logger.error("email processing failed", messageId=message_id, error=str(error))
            _record_error(db, message_id, error)
            continue

        if doc.status == "pending":
            summary["created"] += 1
        elif doc.status == "skipped":
            summary["skipped"] += 1
        else:
            summary["unmatched"] += 1
            logger.info("email unmatched", messageId=message_id)

    logger.info("ingest done", **summary)
    return summary
