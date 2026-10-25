from datetime import UTC, datetime

import pytest

from distillo.ingest.mime import ParsedEmail
from distillo.ingest.service import build_email_doc
from distillo.models import EmailDoc

NOW = datetime(2025, 10, 20, tzinfo=UTC)


def _mail(
    from_header: str, body: str = "<p>hello <a href='https://e.com/a'>A</a></p>"
) -> ParsedEmail:
    return ParsedEmail(from_header=from_header, subject="S", date=NOW, body=body, is_html=True)


def test_pending_for_enabled_source() -> None:
    doc = build_email_doc(_mail("TLDR <dan@tldrnewsletter.com>"), NOW, lambda _: True)
    assert doc.status == "pending"
    assert doc.source_id == "tldr"
    assert "[A](https://e.com/a)" in doc.markdown


def test_skipped_for_disabled_source_has_no_markdown() -> None:
    doc = build_email_doc(_mail("TLDR <dan@tldrnewsletter.com>"), NOW, lambda _: False)
    assert (doc.status, doc.source_id, doc.markdown) == ("skipped", "tldr", "")


def test_unmatched_for_unknown_sender() -> None:
    doc = build_email_doc(_mail("Someone <a@example.com>"), NOW, lambda _: True)
    assert (doc.status, doc.source_id) == ("unmatched", None)


def test_empty_body_for_enabled_source_raises() -> None:
    with pytest.raises(ValueError):
        build_email_doc(_mail("TLDR <dan@tldrnewsletter.com>", body=""), NOW, lambda _: True)


def test_firestore_dict_uses_camel_case_and_from() -> None:
    data = build_email_doc(
        _mail("TLDR <dan@tldrnewsletter.com>"), NOW, lambda _: True
    ).to_firestore()
    assert {"sourceId", "from", "subject", "receivedAt", "markdown", "status", "itemIds"} <= set(
        data
    )
    assert "error" not in data
    assert EmailDoc.model_validate(data).from_address == "TLDR <dan@tldrnewsletter.com>"
