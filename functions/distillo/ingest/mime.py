import base64
import email
import email.policy
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime


@dataclass(frozen=True)
class ParsedEmail:
    from_header: str
    subject: str
    date: datetime | None
    body: str
    is_html: bool  # False = text/plain fallback (or empty body)


def decode_gmail_raw(raw: str) -> bytes:
    """Gmail returns `raw` as base64url, often without padding."""
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def _part_text(part: EmailMessage) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else ""
    except (LookupError, UnicodeDecodeError):
        # unknown charset label or undecodable bytes: lossy utf-8 beats losing the mail
        payload = part.get_payload(decode=True)
        return payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else ""


def _parse_date(value: str) -> datetime | None:
    try:
        return parsedate_to_datetime(value) if value else None
    except (TypeError, ValueError):
        return None


def parse_email(raw: bytes) -> ParsedEmail:
    """Parses RFC 822 bytes (Gmail `raw` once decoded, or the content of an .eml file)."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(message, EmailMessage)

    body_part = message.get_body(preferencelist=("html", "plain"))
    body = ""
    is_html = False
    if isinstance(body_part, EmailMessage):
        body = _part_text(body_part)
        is_html = body_part.get_content_type() == "text/html"

    return ParsedEmail(
        from_header=str(message.get("From", "")),
        subject=str(message.get("Subject", "")),
        date=_parse_date(str(message.get("Date", ""))),
        body=body,
        is_html=is_html,
    )
