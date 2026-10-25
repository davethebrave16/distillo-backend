import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from markdownify import markdownify

_UNSUBSCRIBE_RE = re.compile(
    r"unsubscribe|opt[\s-]?out|manage\s+(your\s+)?(email\s+)?(preferences|subscriptions?)"
    r"|update\s+(your\s+)?(email\s+)?preferences|email\s+preferences",
    re.IGNORECASE,
)
_FOOTER_START_RE = re.compile(
    r"^\s*(you('re|\s+are)\s+receiving\s+this|you\s+received\s+this|to\s+stop\s+receiving"
    r"|if\s+you\s+(no\s+longer|don'?t\s+want|wish\s+to\s+stop)|unsubscribe\b"
    r"|manage\s+(your\s+)?(preferences|subscriptions?)|this\s+email\s+was\s+sent\s+to)",
    re.IGNORECASE,
)
# A sentence cut short by a removed link ("... please ."), found in a short leftover block.
_DANGLING_RE = re.compile(
    r"\b(please|click|here|to|or|and|at|via|from|by)\b[\s.,;:|\-\u2013\u2014]*$", re.IGNORECASE
)
_TRACKING_HOST_RE = re.compile(r"(^|\.)(track|tracking|pixel|open|beacon|trk)\.", re.IGNORECASE)
_HIDDEN_STYLE_RE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|mso-hide\s*:\s*all|opacity\s*:\s*0(?![.\d])"
    r"|max-height\s*:\s*0(px)?\s*(;|$)|font-size\s*:\s*0(px)?\s*(;|$)",
    re.IGNORECASE,
)
# zero-width space/non-joiner/joiner, word joiner, BOM, soft hyphen, combining grapheme joiner
_INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00ad\u034f]")
_SPACE_RUN_RE = re.compile(r"[ \t\u00a0\u2007\u2009\u202f]+")
_FOOTER_SEARCH_FROM = 0.6  # a footer marker only counts in the last 40% of the document
_DANGLING_MAX_CHARS = 300  # only short leftover blocks are treated as orphans
_BLOCK_NAMES = ("div", "section", "article", "header", "footer", "center", "tr", "td", "th")
_TABLE_PARTS = ("table", "thead", "tbody", "tfoot", "tr", "td", "th")
_NO_CLEAN_PARENTS = {"pre", "code"}


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
    if _HIDDEN_STYLE_RE.search(_attr(img, "style")):
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
    markdown = _INVISIBLE_RE.sub("", markdown)
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)
    return re.sub(r"\n{3,}", "\n\n", markdown).strip()


def _clean_text_nodes(soup: BeautifulSoup) -> None:
    """Strips invisible characters (preheader padding) and collapses space runs, outside code."""
    for node in soup.find_all(string=True):
        if not isinstance(node, NavigableString) or node.parent is None:
            continue
        if any(p.name in _NO_CLEAN_PARENTS for p in node.parents if isinstance(p, Tag)):
            continue
        cleaned = _SPACE_RUN_RE.sub(" ", _INVISIBLE_RE.sub("", str(node)))
        if cleaned != str(node):
            node.replace_with(cleaned)


def _unwrap_layout(soup: BeautifulSoup) -> None:
    """Turns layout tables and block containers into paragraphs; keeps tables with <th> cells."""
    # a table is a data table only if a <th> belongs to it directly (not to a table nested inside)
    data_tables = {id(th.find_parent("table")) for th in soup.find_all("th")}
    for tag in soup.find_all(_TABLE_PARTS + _BLOCK_NAMES):
        if tag.name in _TABLE_PARTS:
            owner = tag if tag.name == "table" else tag.find_parent("table")
            if owner is not None and id(owner) in data_tables:
                continue
        if tag.name in ("table", "thead", "tbody", "tfoot"):
            tag.unwrap()  # wrappers add no boundary of their own; rows and cells do
        else:
            tag.name = "p"  # block boundary → paragraph break


def _drop_unsubscribe_links(soup: BeautifulSoup) -> None:
    parents: list[Tag] = []
    for link in soup.find_all("a"):
        if _UNSUBSCRIBE_RE.search(_attr(link, "href")) or _UNSUBSCRIBE_RE.search(
            link.get_text(" ", strip=True)
        ):
            block = link.find_parent(["p", "li", "div", "td", "th"])
            if block is not None:
                parents.append(block)
            link.decompose()
    # drop short leftovers such as "... or if this isn't for you, please ."
    for block in parents:
        if block.parent is None:
            continue
        text = block.get_text(" ", strip=True)
        if not re.search(r"\w", text) or (
            len(text) <= _DANGLING_MAX_CHARS and _DANGLING_RE.search(text) and not block.find("a")
        ):
            block.decompose()


def html_to_markdown(html: str) -> str:
    """HTML → readable markdown without tracking pixels, unsubscribe links and the legal footer.

    Layout tables are flattened into paragraphs (only tables with <th> cells stay tables), invisible
    padding characters are removed and tracking URLs are left untouched (step 2 resolves them).
    "View in browser" links are kept: step 2 uses them as the item URL of essay sources.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "head", "title", "noscript", "iframe"]):
        tag.decompose()
    for tag in soup.find_all(style=_HIDDEN_STYLE_RE):
        tag.decompose()
    for img in soup.find_all("img"):
        if _is_tracking_image(img):
            img.decompose()
    _drop_unsubscribe_links(soup)
    _clean_text_nodes(soup)
    _unwrap_layout(soup)
    return _tidy(strip_footer(markdownify(str(soup), heading_style="ATX")))


def plain_text_to_markdown(text: str) -> str:
    return _tidy(strip_footer(text.replace("\r\n", "\n")))
