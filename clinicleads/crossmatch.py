"""Find hospital consultants who also run their own practice.

Input: a roster CSV (doctor_name, specialty, hospital, city, source_url) read from
hospitals' public "our doctors" pages, and the clinics already collected for the
same city. A clinic named after a rostered doctor ("Dr Anita Rao's Skin Clinic")
is a candidate. Every candidate is a suggestion for a human to confirm - two
doctors can share a name.
"""
from __future__ import annotations

import csv

from .model import Lead, norm_text, person_tokens

# Too common to match on surname + initial alone.
COMMON = {
    "singh", "kumar", "sharma", "gupta", "das", "khan", "patel", "shah", "reddy",
    "rao", "jain", "verma", "mehta", "roy", "ghosh", "iyer", "nair", "ali",
    "smith", "jones", "brown", "lee", "wong", "tan", "lim", "nguyen", "ahmed",
    "mohammed", "mohamed", "hussain", "williams", "johnson", "taylor",
}


def load_roster(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (r.get("doctor_name") or "").strip()]


def match_strength(doctor: str, clinic_text: str) -> str:
    """'strong' = first name and surname both in the clinic name;
    'weak' = surname + first initial, uncommon surname only; '' = no match."""
    parts = person_tokens(doctor)
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    words = set(norm_text(clinic_text).split())
    if last not in words or len(last) < 3:
        return ""
    if len(first) >= 3 and first in words:
        return "strong"
    if last not in COMMON and first[:1] in {w for w in words if len(w) == 1}:
        return "weak"
    return ""


def crossmatch(roster: list[dict], leads: list[Lead]) -> list[tuple[Lead, dict, str]]:
    """Return (clinic lead, roster row, strength). Hospitals are never matched."""
    hits = []
    for row in roster:
        city = norm_text(row.get("city", ""))
        hospital = norm_text(row.get("hospital", ""))
        for lead in leads:
            if lead.kind == "hospital":
                continue
            if city and norm_text(lead.city) != city:
                continue
            text = f"{lead.name} {lead.operator}"
            if hospital and hospital in norm_text(text):
                continue        # the hospital's own department, not a private practice
            strength = match_strength(row["doctor_name"], text)
            if strength:
                hits.append((lead, row, strength))
    return hits


def apply(roster: list[dict], leads: list[Lead]) -> int:
    """Write the evidence onto matched leads. Returns the number matched."""
    n = 0
    for lead, row, strength in crossmatch(roster, leads):
        lead.consultant_match = (
            f"{strength}: {row['doctor_name'].strip()} ({row.get('specialty', '').strip()}) "
            f"at {row.get('hospital', '').strip()} - {row.get('source_url', '').strip()}"
        )
        n += 1
    return n
