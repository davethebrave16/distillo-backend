import pytest

from distillo.sources.registry import SOURCES, SourceDef, SourceMatch, match_source


def _id(header: str) -> str | None:
    source = match_source(header)
    return source.id if source else None


def test_matches_tldr_by_exact_address_and_by_domain() -> None:
    assert _id("TLDR <dan@tldrnewsletter.com>") == "tldr"
    assert _id("TLDR AI <ai@tldrnewsletter.com>") == "tldr"


def test_is_case_insensitive() -> None:
    assert _id("TLDR <DAN@TLDRNewsletter.com>") == "tldr"
    assert _id("Techpresso <Techpresso@Dupple.com>") == "techpresso"


def test_techpresso_matches_only_its_exact_address() -> None:
    assert _id("Techpresso <techpresso@dupple.com>") == "techpresso"
    assert _id("Other <other@dupple.com>") is None


def test_accepts_bare_and_quoted_addresses() -> None:
    assert _id("dan@tldrnewsletter.com") == "tldr"
    assert _id('"Dan, TLDR" <dan@tldrnewsletter.com>') == "tldr"


@pytest.mark.parametrize(
    "header",
    ["", "not an address", "x <a@nottldrnewsletter.com>", "x <a@tldrnewsletter.com.evil.io>"],
)
def test_no_match(header: str) -> None:
    assert match_source(header) is None


def test_exact_address_beats_earlier_domain_match(monkeypatch: pytest.MonkeyPatch) -> None:
    domain_first = SourceDef("a", "A", "tech", "digest", SourceMatch(from_domains=("x.com",)))
    address_second = SourceDef("b", "B", "tech", "digest", SourceMatch(from_addresses=("n@x.com",)))
    monkeypatch.setattr("distillo.sources.registry.SOURCES", (domain_first, address_second))
    assert _id("n@x.com") == "b"
    assert _id("other@x.com") == "a"


def test_registry_ids_are_unique() -> None:
    ids = [s.id for s in SOURCES]
    assert len(ids) == len(set(ids))
