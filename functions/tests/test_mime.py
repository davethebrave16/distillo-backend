import base64
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from distillo.ingest.mime import decode_gmail_raw, parse_email


def _alternative(plain: str, html: str) -> MIMEMultipart:
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(plain, "plain", "utf-8"))
    alt.attach(MIMEText(html, "html", "utf-8"))
    return alt


def test_nested_multipart_prefers_html() -> None:
    related = MIMEMultipart("related")
    related.attach(_alternative("plain body", "<p>html body</p>"))
    mixed = MIMEMultipart("mixed")
    mixed["From"] = "TLDR <dan@tldrnewsletter.com>"
    mixed["Subject"] = "Hello"
    mixed["Date"] = "Mon, 20 Oct 2025 08:00:00 +0000"
    mixed.attach(related)
    pdf = EmailMessage()
    pdf.set_content(b"%PDF", maintype="application", subtype="pdf", filename="a.pdf")
    mixed.attach(pdf)

    parsed = parse_email(mixed.as_bytes())

    assert parsed.is_html
    assert "<p>html body</p>" in parsed.body
    assert parsed.from_header == "TLDR <dan@tldrnewsletter.com>"
    assert parsed.subject == "Hello"
    assert parsed.date is not None and parsed.date.year == 2025


def test_falls_back_to_plain_when_no_html() -> None:
    msg = EmailMessage()
    msg["From"] = "a@b.co"
    msg.set_content("only plain")

    parsed = parse_email(msg.as_bytes())

    assert not parsed.is_html
    assert parsed.body.strip() == "only plain"


def test_decodes_non_utf8_charset() -> None:
    raw = (
        b"From: a@b.co\r\nSubject: x\r\nMIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=iso-8859-1\r\n"
        b"Content-Transfer-Encoding: 8bit\r\n\r\ncaf\xe9\r\n"
    )
    assert parse_email(raw).body.strip() == "café"


def test_unknown_charset_does_not_raise() -> None:
    raw = (
        b"From: a@b.co\r\nMIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=bogus-99\r\n"
        b"Content-Transfer-Encoding: 8bit\r\n\r\nhello\r\n"
    )
    assert parse_email(raw).body.strip() == "hello"


def test_encoded_headers_are_decoded() -> None:
    raw = b"From: =?utf-8?q?Caf=C3=A9?= <a@b.co>\r\nSubject: =?utf-8?q?Caf=C3=A9?=\r\n\r\nbody\r\n"
    parsed = parse_email(raw)
    assert parsed.subject == "Café"
    assert "Café" in parsed.from_header


def test_missing_body_and_bad_date_are_tolerated() -> None:
    parsed = parse_email(
        b"From: a@b.co\r\nDate: not a date\r\nContent-Type: application/pdf\r\n\r\nx"
    )
    assert parsed.body == ""
    assert parsed.date is None


def test_decode_gmail_raw_handles_base64url_without_padding() -> None:
    original = b"Subject: \xfb\xff\xfe?>\r\n\r\nbody"
    encoded = base64.urlsafe_b64encode(original).decode().rstrip("=")
    assert decode_gmail_raw(encoded) == original
