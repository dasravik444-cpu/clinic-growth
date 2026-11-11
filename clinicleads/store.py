"""SQLite store with de-duplication, and CSV / Excel export."""
from __future__ import annotations

import csv
import math
import sqlite3

from .model import FIELDS, Lead, norm_text, phone_key, score

SCHEMA = "CREATE TABLE IF NOT EXISTS leads (" + ", ".join(
    f"{f} {'REAL' if f in ('lat', 'lon') else 'INTEGER' if f in ('owner_named', 'chain', 'score') else 'TEXT'}"
    for f in FIELDS) + ", PRIMARY KEY (source, source_id))"


def connect(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute(SCHEMA)
    return db


def _metres(a: Lead, b: Lead) -> float:
    if None in (a.lat, a.lon, b.lat, b.lon):
        return float("inf")
    dy = (a.lat - b.lat) * 111_320
    dx = (a.lon - b.lon) * 111_320 * math.cos(math.radians(a.lat))
    return math.hypot(dx, dy)


def dedupe(leads: list[Lead]) -> list[Lead]:
    """Drop repeats: same source id, same phone + name, or same name within 150 m.
    The copy with more contact routes is kept."""
    def richness(l: Lead) -> int:
        return sum(bool(x) for x in (l.phone, l.email, l.website, l.whatsapp, l.address))

    kept: list[Lead] = []
    seen_ids: set = set()
    by_name: dict[tuple, list[Lead]] = {}
    for lead in sorted(leads, key=richness, reverse=True):
        key = (lead.source, lead.source_id)
        if key in seen_ids:
            continue
        nkey = (lead.cc, norm_text(lead.name))
        dup = False
        for other in by_name.get(nkey, []):
            same_phone = phone_key(lead.phone) and phone_key(lead.phone) == phone_key(other.phone)
            if same_phone or _metres(lead, other) <= 150:
                dup = True
                break
        if dup:
            continue
        seen_ids.add(key)
        by_name.setdefault(nkey, []).append(lead)
        kept.append(lead)
    return kept


def save(db: sqlite3.Connection, leads: list[Lead]) -> int:
    cols = ", ".join(FIELDS)
    marks = ", ".join("?" for _ in FIELDS)
    with db:
        for lead in leads:
            score(lead)
            row = lead.row()
            db.execute(f"INSERT OR REPLACE INTO leads ({cols}) VALUES ({marks})",
                       [row[f] for f in FIELDS])
    return len(leads)


def load(db: sqlite3.Connection, where: str = "", args: tuple = ()) -> list[Lead]:
    sql = "SELECT * FROM leads" + (f" WHERE {where}" if where else "")
    return [Lead(**{f: r[f] for f in FIELDS}) for r in db.execute(sql, args)]


def export(leads: list[Lead], path: str) -> int:
    """.xlsx when the name ends so and openpyxl is installed, otherwise CSV."""
    rows = sorted((l.row() for l in leads), key=lambda r: -r["score"])
    if path.lower().endswith(".xlsx"):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Leads"
        ws.append(FIELDS)
        for r in rows:
            ws.append([r[f] for f in FIELDS])
        ws.freeze_panes = "A2"
        wb.save(path)
    else:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows)
    return len(rows)
