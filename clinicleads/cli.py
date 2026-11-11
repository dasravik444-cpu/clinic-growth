"""Command line: python -m clinicleads <command>."""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time

from . import crossmatch as cm
from . import enrich as en
from . import npi, overpass, store
from .net import FetchError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "leads.sqlite")
CITIES = os.path.join(ROOT, "config", "cities.csv")


def load_cities(path: str = CITIES) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pick(cities: list[dict], args) -> list[dict]:
    if args.all:
        return cities
    if args.country:
        return [c for c in cities if c["cc"].lower() == args.country.lower()]
    want = {c.lower() for c in args.city or []}
    found = [c for c in cities if c["city"].lower() in want]
    missing = want - {c["city"].lower() for c in found}
    if missing:
        sys.exit(f"Not in config/cities.csv: {', '.join(sorted(missing))}")
    return found


def cmd_collect(args) -> None:
    db = store.connect(args.db)
    chosen = pick(load_cities(), args)
    if not chosen:
        sys.exit("Choose --city NAME, --country CC or --all")
    total = 0
    for i, city in enumerate(chosen):
        try:
            leads = store.dedupe(overpass.collect(city, args.radius_km))
        except FetchError as e:
            print(f"{city['city']}: FAILED - {e}")
            continue
        store.save(db, leads)
        practices = [l for l in leads if l.kind != "hospital"]
        with_route = sum(1 for l in practices if l.phone or l.email or l.website)
        print(f"{city['city']}: {len(practices)} practices ({with_route} with a contact route), "
              f"{len(leads) - len(practices)} hospitals")
        total += len(practices)
        if i < len(chosen) - 1:
            time.sleep(args.pause)
    print(f"Saved {total} practices to {args.db}")


def cmd_npi(args) -> None:
    db = store.connect(args.db)
    city = next((c for c in load_cities() if c["city"].lower() == args.city.lower()),
                {"city": args.city, "country": "United States", "cc": "US",
                 "review_offer": "allowed-with-rules"})
    leads = store.dedupe(npi.collect(city, args.state))
    store.save(db, leads)
    multi = sum(1 for l in leads if l.consultant_match)
    print(f"{args.city}, {args.state}: {len(leads)} clinicians, {multi} filing more than one practice location")


def cmd_enrich(args) -> None:
    db = store.connect(args.db)
    todo = store.load(db, "website != '' AND email = '' AND kind != 'hospital' AND chain = 0")
    todo = sorted(todo, key=lambda l: -l.score)[: args.limit]
    changed = 0
    for lead in todo:
        if en.enrich(lead):
            store.save(db, [lead])
            changed += 1
        time.sleep(args.pause)
    print(f"Read {len(todo)} clinic websites, added contact details to {changed}")


def cmd_crossmatch(args) -> None:
    db = store.connect(args.db)
    leads = store.load(db)
    n = cm.apply(cm.load_roster(args.roster), leads)
    store.save(db, [l for l in leads if l.consultant_match])
    print(f"{n} clinics matched to a rostered hospital doctor - confirm each before outreach")


def cmd_export(args) -> None:
    db = store.connect(args.db)
    where, params = ["kind != 'hospital'", "score >= ?"], [args.min_score]
    if args.country:
        where.append("cc = ?")
        params.append(args.country.upper())
    if args.consultants:
        where.append("consultant_match != ''")
    leads = store.load(db, " AND ".join(where), tuple(params))
    print(f"Wrote {store.export(leads, args.out)} leads to {args.out}")


def cmd_hospitals(args) -> None:
    """List hospitals with websites: the pages to read for doctor rosters."""
    db = store.connect(args.db)
    for l in store.load(db, "kind = 'hospital' AND website != ''"):
        print(f"{l.city}\t{l.name}\t{l.website}")


def cmd_stats(args) -> None:
    db = store.connect(args.db)
    q = ("SELECT country, COUNT(*) n, SUM(phone != '') ph, SUM(email != '') em, "
         "SUM(website != '') web, SUM(consultant_match != '') cons FROM leads "
         "WHERE kind != 'hospital' GROUP BY country ORDER BY n DESC")
    print(f"{'country':24}{'leads':>7}{'phone':>7}{'email':>7}{'site':>7}{'consult':>8}")
    for r in db.execute(q):
        print(f"{r['country'][:23]:24}{r['n']:>7}{r['ph']:>7}{r['em']:>7}{r['web']:>7}{r['cons']:>8}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="clinicleads", description=__doc__)
    p.add_argument("--db", default=DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("collect", help="clinics, dentists, doctors, hospitals from OpenStreetMap")
    c.add_argument("--city", action="append")
    c.add_argument("--country", help="two-letter code, e.g. IN")
    c.add_argument("--all", action="store_true")
    c.add_argument("--radius-km", type=float)
    c.add_argument("--pause", type=float, default=10)
    c.set_defaults(fn=cmd_collect)

    n = sub.add_parser("npi", help="US clinicians from the public NPI registry")
    n.add_argument("--city", default="Washington")
    n.add_argument("--state", default="DC")
    n.set_defaults(fn=cmd_npi)

    e = sub.add_parser("enrich", help="read clinics' own websites for emails / phones")
    e.add_argument("--limit", type=int, default=200)
    e.add_argument("--pause", type=float, default=2)
    e.set_defaults(fn=cmd_enrich)

    x = sub.add_parser("crossmatch", help="match a hospital doctor roster to private clinics")
    x.add_argument("roster")
    x.set_defaults(fn=cmd_crossmatch)

    o = sub.add_parser("export", help="write leads to .csv or .xlsx, best first")
    o.add_argument("out")
    o.add_argument("--min-score", type=int, default=0)
    o.add_argument("--country")
    o.add_argument("--consultants", action="store_true", help="only hospital consultants with own practice")
    o.set_defaults(fn=cmd_export)

    sub.add_parser("hospitals", help="hospital websites to read for rosters").set_defaults(fn=cmd_hospitals)
    sub.add_parser("stats", help="counts per country").set_defaults(fn=cmd_stats)

    args = p.parse_args(argv)
    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    args.fn(args)
