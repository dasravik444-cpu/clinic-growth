"""US NPI Registry (public, free, no key): individual clinicians with practice address and phone.

A clinician who files more than one practice location, and whose main address is not a hospital,
is a strong sign of a practice of their own.
"""
from __future__ import annotations

import time
import urllib.parse

from .net import fetch_json

API = "https://npiregistry.cms.hhs.gov/api/"
COLUMNS = ["NPI", "Name", "Specialty", "Phone", "Address", "Extra Practice Locations", "Own Practice Signal", "Source"]
TAXONOMIES = ["Dentist", "Dermatology", "Orthodontics", "Ophthalmology", "Plastic Surgery", "Family Medicine",
              "Internal Medicine", "Obstetrics & Gynecology", "Orthopaedic Surgery", "Pediatrics"]
HOSPITAL_WORDS = ("hospital", "medical center", "medical centre", "health system", "university", "va medical")


def parse(payload: dict, taxonomy: str = "") -> list[dict]:
    out = []
    for r in payload.get("results", []):
        basic = r.get("basic") or {}
        if (basic.get("status") or "A") != "A":
            continue
        locs = [a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"]
        if not locs:
            continue
        loc = locs[0]
        tax = next((t for t in r.get("taxonomies", []) if t.get("primary")), None) or (r.get("taxonomies") or [{}])[0]
        street = " ".join(p for p in (loc.get("address_1"), loc.get("address_2")) if p)
        extra = len(r.get("practiceLocations") or [])
        at_hospital = any(w in street.lower() for w in HOSPITAL_WORDS)
        out.append({
            "NPI": str(r.get("number")),
            "Name": " ".join(p for p in ("Dr.", basic.get("first_name", "").title(),
                                         basic.get("last_name", "").title()) if p),
            "Specialty": tax.get("desc") or taxonomy,
            "Phone": loc.get("telephone_number", ""),
            "Address": ", ".join(p for p in (street.title(), loc.get("city", "").title(), loc.get("state"),
                                             (loc.get("postal_code") or "")[:5]) if p),
            "Extra Practice Locations": extra,
            "Own Practice Signal": "yes" if extra and not at_hospital else "",
            "Source": f"https://npiregistry.cms.hhs.gov/provider-view/{r.get('number')}",
        })
    return out


def collect(city: str, state: str, taxonomies=None, max_per_taxonomy: int = 1200, pause: float = 1.0) -> list[dict]:
    """The API returns 200 rows a page and at most 1,200 rows per search."""
    out, seen = [], set()
    for tax in taxonomies or TAXONOMIES:
        skip = 0
        while skip < max_per_taxonomy:
            qs = urllib.parse.urlencode({"version": "2.1", "city": city, "state": state, "taxonomy_description": tax,
                                         "enumeration_type": "NPI-1", "limit": 200, "skip": skip})
            payload = fetch_json(f"{API}?{qs}", timeout=60)
            for row in parse(payload, tax):
                if row["NPI"] not in seen:
                    seen.add(row["NPI"])
                    out.append(row)
            if len(payload.get("results") or []) < 200:
                break
            skip += 200
            time.sleep(pause)
    return out
