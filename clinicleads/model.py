"""Lead record, scoring and name helpers. Standard library only."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

FIELDS = [
    "source", "source_id", "kind", "name", "specialty", "phone", "email", "website",
    "whatsapp", "address", "city", "country", "cc", "lat", "lon", "operator",
    "opening_hours", "source_url", "fetched_at", "review_offer",
    "owner_named", "chain", "score", "score_reasons", "consultant_match",
]


@dataclass
class Lead:
    source: str
    source_id: str
    kind: str = "clinic"            # dentist | clinic | doctor | hospital | other
    name: str = ""
    specialty: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    whatsapp: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    cc: str = ""
    lat: float | None = None
    lon: float | None = None
    operator: str = ""
    opening_hours: str = ""
    source_url: str = ""
    fetched_at: str = ""
    review_offer: str = ""
    owner_named: int = 0
    chain: int = 0
    score: int = 0
    score_reasons: str = ""
    consultant_match: str = ""
    extra: dict = field(default_factory=dict, repr=False)

    def row(self) -> dict:
        d = asdict(self)
        d.pop("extra", None)
        return d


# Specialties where one extra kept appointment is worth a lot to the clinic,
# so a monthly fee is easy to justify.
HIGH_VALUE = (
    "dent", "orthodon", "implant", "dermat", "skin", "cosmet", "plastic", "aesthet",
    "hair", "fertil", "ivf", "ophthal", "eye", "lasik", "orthop", "physio",
    "bariatric", "ent", "gyn", "obstet",
)

# Large groups buy centrally; a single-branch pitch rarely lands.
CHAINS = (
    "apollo", "fortis", "max healthcare", "max hospital", "manipal", "narayana",
    "medanta", "clove dental", "sabka dentist", "practo", "dr lal", "lal pathlabs",
    "thyrocare", "metropolis", "aster", "nmc health", "mediclinic", "bupa",
    "mydentist", "aspen dental", "heartland dental", "pacific dental", "kaiser",
    "medstar", "nhs", "spire", "nuffield", "hca", "pacific smiles", "1300smiles",
    "q&m", "raffles medical", "healthway", "netcare", "life healthcare",
)

_DR = re.compile(r"\b(dr|doctor|prof|professor)\b\.?", re.I)
_DEGREES = re.compile(
    r"\b(mbbs|md|ms|mds|bds|dnb|dm|mch|frcs|mrcp|mrcs|facs|phd|dds|dmd|do|mbchb|fracs|fracp)\b\.?",
    re.I,
)


def norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


def is_owner_named(name: str) -> bool:
    """'Dr. Mehta's Dental Clinic' -> the owner is the decision maker."""
    return bool(_DR.search(name or ""))


def is_chain(name: str, brand: str = "") -> bool:
    n = norm_text(name + " " + brand)
    return bool(brand.strip()) or any(norm_text(c) in n for c in CHAINS)


def person_tokens(name: str) -> list[str]:
    """Name parts of a doctor, without titles, degrees and punctuation."""
    s = _DEGREES.sub(" ", _DR.sub(" ", name or ""))
    return [t for t in norm_text(s).split() if t]


def phone_key(phone: str) -> str:
    """Digits only, last 10 - used to spot duplicates, never shown as a number."""
    d = re.sub(r"\D", "", (phone or "").split(";")[0])
    return d[-10:] if len(d) >= 7 else ""


def score(lead: Lead) -> Lead:
    """0-100. Higher = easier to reach and more likely to pay. Reasons are kept."""
    if lead.kind == "hospital":
        lead.score, lead.score_reasons = 0, "hospital: roster source, not a lead"
        return lead
    pts, why = 0, []

    def add(n: int, reason: str) -> None:
        nonlocal pts
        pts += n
        why.append(f"{'+' if n >= 0 else ''}{n} {reason}")

    if lead.phone:
        add(25, "phone")
    if lead.email:
        add(20, "email")
    if lead.website:
        add(15, "website")
    if lead.whatsapp:
        add(5, "whatsapp link")
    lead.owner_named = int(is_owner_named(lead.name) or is_owner_named(lead.operator))
    if lead.owner_named:
        add(15, "owner-named practice")
    words = norm_text(f"{lead.kind} {lead.specialty} {lead.name}").split()
    # long keys match the start of a word ("dent" -> dentist, dental); short ones a whole word
    if any((w.startswith(k) if len(k) > 3 else w == k) for w in words for k in HIGH_VALUE):
        add(15, "high-value specialty")
    if lead.opening_hours:
        add(5, "hours listed")
    if lead.consultant_match:
        add(15, "hospital consultant with own practice")
    if lead.chain:
        add(-30, "chain/group")
    if not (lead.phone or lead.email or lead.website):
        add(-20, "no contact route")
    lead.score = max(0, min(100, pts))
    lead.score_reasons = "; ".join(why)
    return lead
