"""Clinic lead commands:  python -m clinicleads <command>

  cities                     the cities that are set up
  find CITY                  one run of the lead finder for a city (one part of the city per run)
  status CITY                how far that city is
  export CITY                write data/leads-CITY.csv
  hospitals CITY             hospitals found there, with websites (read these for doctor rosters)
  consultants CITY ROSTER    clinics named after a rostered hospital doctor -> data/consultants-CITY.csv
  npi CITY STATE             US clinicians from the public NPI registry -> data/npi-CITY.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import subprocess
import sys

from . import crossmatch as cm
from . import npi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEAD_COLUMNS_SHOWN = ["Business Name", "Website", "Phones", "Emails"]


def city_config(slug: str) -> str:
    hits = [p for p in glob.glob(os.path.join(ROOT, "config", "??", f"{slug}.toml"))]
    if len(hits) != 1:
        known = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "config", "??", "*.toml"))
                       if not os.path.basename(p).startswith("_"))
        sys.exit(f"Unknown city '{slug}'. Set up: {', '.join(known)}")
    return hits[0]


def paths(slug: str) -> tuple[str, str, str]:
    cfg = city_config(slug)
    cc = os.path.basename(os.path.dirname(cfg))
    return cfg, os.path.join(ROOT, "state", f"{cc}-{slug}.sqlite"), os.path.join(ROOT, "data", f"leads-{slug}.csv")


def leadgen(*args: str) -> int:
    return subprocess.call([sys.executable, "-m", "leadgen", *args], cwd=ROOT)


def export(slug: str) -> str:
    cfg, db, out = paths(slug)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if leadgen("export-csv", "--config", cfg, "--db", db, "--out", out):
        sys.exit("export failed")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m clinicleads", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cities")
    for name in ("find", "status", "export", "hospitals"):
        sub.add_parser(name).add_argument("city")
    f = sub.choices["find"]
    f.add_argument("--no-sheets", action="store_true", help="keep leads on this device only")
    f.add_argument("--budget-minutes", type=float)
    c = sub.add_parser("consultants")
    c.add_argument("city")
    c.add_argument("roster")
    n = sub.add_parser("npi")
    n.add_argument("city")
    n.add_argument("state")
    a = ap.parse_args(argv)

    if a.cmd == "cities":
        with open(os.path.join(ROOT, "config", "cities.csv"), newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                print(f"{r['slug']:22}{r['country']:22}review offer: {r['review_offer']}")
    elif a.cmd == "find":
        cfg, db, _ = paths(a.city)
        os.makedirs(os.path.dirname(db), exist_ok=True)
        extra = (["--no-sheets"] if a.no_sheets else []) + \
                (["--budget-minutes", str(a.budget_minutes)] if a.budget_minutes else [])
        sys.exit(leadgen("run", "--config", cfg, "--db", db, *extra))
    elif a.cmd == "status":
        cfg, db, _ = paths(a.city)
        sys.exit(leadgen("status", "--config", cfg, "--db", db))
    elif a.cmd == "export":
        print(f"Wrote {export(a.city)}")
    elif a.cmd == "hospitals":
        rows = cm.hospitals(cm.read_csv(export(a.city)))
        for r in rows:
            print(f"{r['Business Name']}\t{r.get('Website', '')}")
        print(f"{len(rows)} hospitals. Read each one's doctors page into rosters/{a.city}.csv "
              f"(columns: {', '.join(cm.ROSTER_COLUMNS)})")
    elif a.cmd == "consultants":
        leads = cm.read_csv(export(a.city))
        hits = cm.crossmatch(cm.load_roster(a.roster), leads)
        out = os.path.join(ROOT, "data", f"consultants-{a.city}.csv")
        cm.write_csv(hits, out, cm.EXTRA_COLUMNS + list(leads[0].keys() if leads else []))
        strong = sum(1 for h in hits if h["Consultant Match"] == "strong")
        print(f"{len(hits)} clinics matched a rostered doctor ({strong} strong). Confirm each before contact: {out}")
    elif a.cmd == "npi":
        rows = npi.collect(a.city, a.state)
        out = os.path.join(ROOT, "data", f"npi-{a.city.lower().replace(' ', '-')}.csv")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cm.write_csv(rows, out, npi.COLUMNS)
        own = sum(1 for r in rows if r["Own Practice Signal"])
        print(f"{len(rows)} clinicians, {own} with an own-practice signal: {out}")
