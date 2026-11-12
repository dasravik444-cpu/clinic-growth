"""Name helpers shared by the consultant tools. Standard library only."""
from __future__ import annotations

import re

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


def person_tokens(name: str) -> list[str]:
    """Name parts of a doctor, without titles, degrees and punctuation."""
    s = _DEGREES.sub(" ", _DR.sub(" ", name or ""))
    return [t for t in norm_text(s).split() if t]
