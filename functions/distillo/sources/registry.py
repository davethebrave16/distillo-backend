from dataclasses import dataclass
from email.utils import parseaddr
from typing import Literal

SourceKind = Literal["digest", "essay"]
# digest = newsletter con N link ad articoli esterni (es. TLDR)
# essay  = newsletter che È l'articolo (es. long-form): l'item è la newsletter stessa


@dataclass(frozen=True)
class SourceMatch:
    from_addresses: tuple[str, ...] = ()  # match esatto sul mittente (case-insensitive)
    from_domains: tuple[str, ...] = ()  # match sul dominio del mittente


@dataclass(frozen=True)
class SourceDef:
    id: str  # slug stabile, usato come chiave ovunque
    name: str
    category: str  # dominio ("tech", ...); abilita estensione futura oltre il tech
    kind: SourceKind
    match: SourceMatch
    extract_hints: str | None = None  # istruzioni extra per l'LLM


SOURCES: tuple[SourceDef, ...] = (
    SourceDef(
        id="tldr",
        name="TLDR",
        category="tech",
        kind="digest",
        match=SourceMatch(
            from_addresses=("dan@tldrnewsletter.com",),
            from_domains=("tldrnewsletter.com",),
        ),
        extract_hints="Ignore Sponsor blocks and job listing sections.",
    ),
    SourceDef(
        id="techpresso",
        name="Techpresso",
        category="tech",
        kind="digest",
        # NON usare from_domains "dupple.com": lo stesso dominio pubblica altre newsletter
        match=SourceMatch(from_addresses=("techpresso@dupple.com",)),
    ),
    # nuove fonti: aggiungere qui → deploy
)


def match_source(from_header: str) -> SourceDef | None:
    """Estrae l'indirizzo da 'Nome <a@b.c>' (email.utils.parseaddr) e lo confronta col registry.

    Gli indirizzi esatti hanno precedenza sui domini; a parità vince il primo SourceDef.
    """
    address = parseaddr(from_header)[1].strip().lower()
    if "@" not in address:
        return None
    domain = address.rsplit("@", 1)[1]

    for source in SOURCES:
        if address in (a.lower() for a in source.match.from_addresses):
            return source
    for source in SOURCES:
        if domain in (d.lower() for d in source.match.from_domains):
            return source
    return None
