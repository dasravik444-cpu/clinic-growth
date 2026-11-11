"""OpenStreetMap (Overpass API) collector: clinics, doctors, dentists, hospitals.

OSM data is open (ODbL) and carries the contact details the practice or a mapper
published. Coverage is uneven: strong in Europe, patchy in India and the Gulf.
"""
from __future__ import annotations

import datetime as dt

from .model import Lead, is_chain
from .net import FetchError, fetch_json

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

HEALTHCARE = ("clinic|doctor|dentist|centre|physiotherapist|optometrist|"
              "psychotherapist|alternative|dialysis|laboratory")


def build_query(lat: float, lon: float, radius_km: float) -> str:
    r = int(radius_km * 1000)
    a = f"(around:{r},{lat},{lon})"
    return (
        "[out:json][timeout:180];\n(\n"
        f'  nwr["amenity"~"^(clinic|doctors|dentist|hospital)$"]{a};\n'
        f'  nwr["healthcare"~"^({HEALTHCARE})$"]{a};\n'
        ");\nout center tags;"
    )


def _kind(tags: dict) -> str:
    amenity, hc = tags.get("amenity", ""), tags.get("healthcare", "")
    if amenity == "hospital" or hc == "hospital":
        return "hospital"
    if amenity == "dentist" or hc == "dentist":
        return "dentist"
    if amenity == "doctors" or hc == "doctor":
        return "doctor"
    if amenity == "clinic" or hc in ("clinic", "centre"):
        return "clinic"
    return hc or "other"


def _first(tags: dict, *keys: str) -> str:
    for k in keys:
        v = (tags.get(k) or "").strip()
        if v:
            return v
    return ""


def _address(tags: dict) -> str:
    if tags.get("addr:full"):
        return tags["addr:full"].strip()
    parts = [
        " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p),
        tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
        tags.get("addr:city"), tags.get("addr:postcode"),
    ]
    return ", ".join(p.strip() for p in parts if p and p.strip())


def parse(payload: dict, city: dict, fetched_at: str | None = None) -> list[Lead]:
    """Turn an Overpass JSON answer into leads. Unnamed places are skipped."""
    fetched_at = fetched_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out: list[Lead] = []
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        name = _first(tags, "name:en", "name", "official_name")
        if not name:
            continue
        centre = el.get("center") or {}
        lat, lon = el.get("lat", centre.get("lat")), el.get("lon", centre.get("lon"))
        brand = _first(tags, "brand")
        out.append(Lead(
            source="osm",
            source_id=f"{el.get('type')}/{el.get('id')}",
            kind=_kind(tags),
            name=name,
            specialty=_first(tags, "healthcare:speciality", "healthcare:specialty").replace(";", ", "),
            phone=_first(tags, "contact:phone", "phone", "contact:mobile", "mobile"),
            email=_first(tags, "contact:email", "email"),
            website=_first(tags, "contact:website", "website", "url"),
            whatsapp=_first(tags, "contact:whatsapp"),
            address=_address(tags),
            city=city["city"], country=city["country"], cc=city["cc"],
            lat=lat, lon=lon,
            operator=_first(tags, "operator"),
            opening_hours=_first(tags, "opening_hours"),
            source_url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
            fetched_at=fetched_at,
            review_offer=city.get("review_offer", ""),
            chain=int(is_chain(name, brand)),
        ))
    return out


def collect(city: dict, radius_km: float | None = None, endpoints=None) -> list[Lead]:
    """Query the first Overpass server that answers."""
    q = build_query(float(city["lat"]), float(city["lon"]),
                    float(radius_km or city["radius_km"]))
    errors = []
    for url in endpoints or ENDPOINTS:
        try:
            return parse(fetch_json(url, {"data": q}, retries=2), city)
        except FetchError as e:
            errors.append(str(e))
    raise FetchError("all Overpass servers failed: " + " | ".join(errors))
