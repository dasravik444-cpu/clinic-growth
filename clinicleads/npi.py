"""US NPI Registry collector (public, free, no key): individual clinicians.

Each record is one licensed clinician with the practice address and phone they
filed. A clinician who files more than one practice location is a strong sign of
a practice outside their main hospital.
"""
from __future__ import annotations

import datetime as dt
import time
import urllib.parse

from .model import Lead
from .net import fetch_json

API = "https://npiregistry.cms.hhs.gov/api/"
TAXONOMIES = ["Dentist", "Dermatology", "Orthodontics", "Ophthalmology",
              "Plastic Surgery", "Family Medicine", "Internal Medicine",
              "Obstetrics & Gynecology", "Orthopaedic Surgery", "Pediatrics"]
HOSPITAL_WORDS = ("hospital", "medical center", "medical centre", "health system",
                  "university", "va medical")


def parse(payload: dict, city: dict, taxonomy: str, fetched_at: str | None = None) -> list[Lead]:
    fetched_at = fetched_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for r in payload.get("results", []):
        basic = r.get("basic") or {}
        if (basic.get("status") or "A") != "A":
            continue
        locs = [a for a in r.get("addresses", []) if a.get("address_purpose") == "LOCATION"]
        if not locs:
            continue
        loc = locs[0]
        name = " ".join(p for p in ("Dr.", basic.get("first_name", "").title(),
                                    basic.get("last_name", "").title()) if p)
        tax = next((t for t in r.get("taxonomies", []) if t.get("primary")), None) \
            or (r.get("taxonomies") or [{}])[0]
        street = " ".join(p for p in (loc.get("address_1"), loc.get("address_2")) if p)
        extra_sites = len(r.get("practiceLocations") or [])
        at_hospital = any(w in street.lower() for w in HOSPITAL_WORDS)
        match = ""
        if extra_sites and not at_hospital:
            match = f"files {extra_sites + 1} practice locations in NPI registry"
        out.append(Lead(
            source="npi", source_id=str(r.get("number")), kind="doctor",
            name=name, specialty=tax.get("desc") or taxonomy,
            phone=loc.get("telephone_number", ""),
            address=", ".join(p for p in (street.title(), loc.get("city", "").title(),
                                          loc.get("state"), (loc.get("postal_code") or "")[:5]) if p),
            city=city["city"], country=city["country"], cc=city["cc"],
            source_url=f"https://npiregistry.cms.hhs.gov/provider-view/{r.get('number')}",
            fetched_at=fetched_at, review_offer=city.get("review_offer", ""),
            owner_named=1, consultant_match=match,
        ))
    return out


def collect(city: dict, state: str, taxonomies=None, max_per_taxonomy: int = 1200,
            pause: float = 1.0) -> list[Lead]:
    """The API returns 200 rows a page and at most 1,200 rows per search."""
    out: list[Lead] = []
    for tax in taxonomies or TAXONOMIES:
        skip = 0
        while skip < max_per_taxonomy:
            qs = urllib.parse.urlencode({
                "version": "2.1", "city": city["city"], "state": state,
                "taxonomy_description": tax, "enumeration_type": "NPI-1",
                "limit": 200, "skip": skip,
            })
            payload = fetch_json(f"{API}?{qs}", timeout=60)
            rows = payload.get("results") or []
            out.extend(parse(payload, city, tax))
            if len(rows) < 200:
                break
            skip += 200
            time.sleep(pause)
    return out
