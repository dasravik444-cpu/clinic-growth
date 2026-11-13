"""Find hospital consultants who also run their own practice.

Input: a roster CSV (doctor_name, specialty, hospital, source_url) read from a hospital's public
"our doctors" page, and the lead finder's export for the same city. A clinic named after a rostered
doctor ("Dr Anita Rao's Skin Clinic") is a candidate. Every candidate is a suggestion for a human
to confirm - two doctors can share a name.
"""
from __future__ import annotations

import csv
import re

from .model import norm_text, person_tokens

HOSPITAL_LABEL = "Hospital (roster source)"
ROSTER_COLUMNS = ["doctor_name", "specialty", "hospital", "source_url"]
EXTRA_COLUMNS = ["Consultant Match", "Hospital Doctor", "Hospital", "Hospital Specialty", "Roster Source"]

# Too common to match on surname + initial alone.
COMMON = {
    "singh", "kumar", "sharma", "gupta", "das", "khan", "patel", "shah", "reddy",
    "rao", "jain", "verma", "mehta", "roy", "ghosh", "iyer", "nair", "ali",
    "smith", "jones", "brown", "lee", "wong", "tan", "lim", "nguyen", "ahmed",
    "mohammed", "mohamed", "hussain", "williams", "johnson", "taylor",
}


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_roster(path: str) -> list[dict]:
    return [r for r in read_csv(path) if (r.get("doctor_name") or "").strip()]


def match_strength(doctor: str, clinic_text: str) -> str:
    """'strong' = first name and surname both in the clinic name;
    'weak' = surname + first initial, uncommon surname only; '' = no match."""
    parts = person_tokens(doctor)
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    words = set(norm_text(re.sub(r"[’']s\b", " ", clinic_text)).split())
    if last not in words or len(last) < 3:
        return ""
    if len(first) >= 3 and first in words:
        return "strong"
    if last not in COMMON and first[:1] in {w for w in words if len(w) == 1}:
        return "weak"
    return ""


def hospitals(leads: list[dict]) -> list[dict]:
    return [r for r in leads if r.get("Category") == HOSPITAL_LABEL]


def crossmatch(roster: list[dict], leads: list[dict]) -> list[dict]:
    """Lead rows (never hospitals) named after a rostered doctor, with the evidence added."""
    out = []
    for lead in leads:
        if lead.get("Category") == HOSPITAL_LABEL:
            continue
        text = f"{lead.get('Business Name', '')} {lead.get('Contact Person', '')}"
        best = None
        for row in roster:
            hospital = norm_text(row.get("hospital", ""))
            if hospital and hospital in norm_text(text):
                continue        # the hospital's own department, not a private practice
            strength = match_strength(row["doctor_name"], text)
            if strength and (best is None or (strength == "strong" and best[0] == "weak")):
                best = (strength, row)
        if best:
            strength, row = best
            out.append({**lead, "Consultant Match": strength,
                        "Hospital Doctor": row["doctor_name"].strip(),
                        "Hospital": (row.get("hospital") or "").strip(),
                        "Hospital Specialty": (row.get("specialty") or "").strip(),
                        "Roster Source": (row.get("source_url") or "").strip()})
    out.sort(key=lambda r: r["Consultant Match"] != "strong")
    return out


def write_csv(rows: list[dict], path: str, columns: list[str]) -> int:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return len(rows)
