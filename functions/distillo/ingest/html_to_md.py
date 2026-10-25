import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

_UNSUBSCRIBE_RE = re.compile(
    r"unsubscribe|opt[\s-]?out|manage\s+(your\s+)?(email\s+)?(preferences|subscription)"
    r"|update\s+(your\s+)?(email\s+)?preferences|email\s+preferences",
    re.IGNORECASE,
)
_FOOTER_START_RE = re.compile(
    r"^\s*(you('re|\s+are)\s+receiving\s+this|you\s+received\s+this|to\s+stop\s+receiving"
    r"|if\s+you\s+(no\s+longer|don'?t\s+want|wish\s+to\s+stop)|unsubscribe\b"
    r"|manage\s+(your\s+)?(preferences|subscription)|this\s+email\s+was\s+sent\s+to)",
    re.IGNORECASE,
)
_TRACKING_HOST_RE = re.compile(r"(^|\.)(track|tracking|pixel|open|beacon|trk)\.", re.IGNORECASE)
_HIDDEN_RE = re.compile(r"display\s*:\s*none", re.IGNORECASE)
_FOOTER_SEARCH_FROM = 0.6  # a footer marker only counts in the last 40% of the document


def _attr(tag: Tag, name: str) -> str:
    value = tag.get(name)
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        return " ".join(value)
    return ""


def _is_dimension_tiny(value: str) -> bool:
    return value.strip().isdigit() and 0 < int(value) <= 2


def _is_tracking_image(img: Tag) -> bool:
    src = _attr(img, "src").strip()
    alt = _attr(img, "alt").strip()
    if not src or src.startswith("data:"):
        return True
    if _is_dimension_tiny(_attr(img, "width")) or _is_dimension_tiny(_attr(img, "height")):
        return True
    if _HIDDEN_RE.search(_attr(img, "style")):
        return True
    host = re.sub(r"^[a-z]+://", "", src, flags=re.IGNORECASE).split("/", 1)[0]
    if _TRACKING_HOST_RE.search(host):
        return True
    return not alt  # decorative image without alt text: no value for extraction


def strip_footer(markdown: str) -> str:
    lines = markdown.split("\n")
    for i in range(int(len(lines) * _FOOTER_SEARCH_FROM), len(lines)):
        if _FOOTER_START_RE.match(lines[i]):
            return "\n".join(lines[:i])
    return markdown


def _tidy(markdown: str) -> str:
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


def html_to_markdown(html: str) -> str:
    """HTML → markdown without tracking pixels, unsubscribe links and the legal footer.

    "View in browser" links are kept: step 2 uses them as the item URL of essay sources.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "title", "noscript", "iframe"]):
        tag.decompose()
    for img in soup.find_all("img"):
        if _is_tracking_image(img):
            img.decompose()
    for link in soup.find_all("a"):
        if _UNSUBSCRIBE_RE.search(_attr(link, "href")) or _UNSUBSCRIBE_RE.search(
            link.get_text(" ", strip=True)
        ):
            link.decompose()
    return _tidy(strip_footer(markdownify(str(soup), heading_style="ATX")))


def plain_text_to_markdown(text: str) -> str:
    return _tidy(strip_footer(text.replace("\r\n", "\n")))
