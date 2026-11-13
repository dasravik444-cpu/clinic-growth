"""Write the city campaign files into config/<country>/ from config/cities.csv.

    python scripts/make_markets.py

Add a city: add a row to config/cities.csv and run this again. The country must be one the lead
finder knows (leadgen/country.py: IN, US, GB, AU, CA, IE, NZ, AE, SG, DE).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from leadgen.country import SUPPORTED  # noqa: E402

BASE = """# Shared settings of every {country} city (config/{code}/<city>.toml includes this file).
# Made by scripts/make_markets.py.

[campaign]
country = "{cc}"
language = "en"
region = "{region}"

[sheets]
enabled = true
leads_tab = "Clinics {cc}"
plan_tab = ""
report_tab = "Lead Report"
require_any = ["email", "whatsapp", "phone"]   # a clinic we can reach by any of these goes into the Sheet
checkpoint_minutes = 20

[filters]
require_contact = true
exclude_closed = true
allow_unmatched_categories = false
# Clinic, dental and lab chains decide centrally - poor leads. Hospital groups are left in on purpose:
# hospitals are roster sources, not leads.
exclude_chains = [
  "clove dental", "sabka dentist", "apollo clinic", "apollo dental", "apollo pharmacy", "apollo diagnostics",
  "dr lal pathlabs", "lal path", "thyrocare", "metropolis", "srl diagnostics", "healthians", "practo",
  "vlcc", "kaya", "oliva", "dr batra", "vasan eye", "lenskart", "titan eye", "medplus", "wellness forever",
  "mydentist", "bupa dental", "portman dental", "specsavers", "boots", "vision express", "optical express",
  "aspen dental", "heartland dental", "pacific dental", "western dental", "smile direct", "kaiser",
  "cvs", "walgreens", "minuteclinic", "concentra", "one medical", "carbon health", "labcorp", "quest diagnostics",
  "pacific smiles", "1300smiles", "maven dental", "national dental care", "opsm", "q&m dental", "raffles medical",
  "healthway medical", "aster clinic", "nmc medical", "mediclinic", "lifelabs", "dynacare", "centric health",
]
exclude_name_words = ["pharmacy", "chemist", "medical store", "medicos", "druggist", "veterinary", "vet clinic",
                      "pet clinic", "animal", "blood bank", "ambulance", "government", "govt", "municipal",
                      "dispensary", "primary health", "esi ", "cghs", "anganwadi", "pathology", "diagnostic"]

[plan]
days = 2                 # each city is split into 2 parts, the centre first; one run does one part
daily_target = "auto"
order = "center_out"
min_cell_km = 1.0
max_cell_km = 8.0
split_threshold = 60
finish_scheduled_part = true

[compliance]
mode = "open-data"       # Overture Maps + OpenStreetMap + the practices' own websites (no Google scraping)

[open_data]
min_confidence = 0.5
refresh_days = 30
# Members of the health categories that are not practices we sell to.
exclude_codes = ["optometry", "eyewear_store", "nursing", "audiology", "home_health_care", "medical_transportation",
                 "blood_and_plasma_donation_center", "health_insurance_office", "ambulance_or_ems_service",
                 "abuse_and_addiction_treatment_center", "alcohol_and_drug_treatment_center", "public_health_clinic",
                 "diagnostic_imaging", "laboratory_testing", "radiology", "pharmacy", "veterinarian", "hospice",
                 "prosthetics", "counseling", "naturopathic_medicine"]

[enrich]
website = true
max_pages_per_site = 6
social_search = false
instagram_profile = false
check_email_mx = true
role_email_candidates = false   # no guessed info@ addresses
email_hunt = true
email_archive = true
email_search = false
workers = 6
site_interval_s = 2.0

[crawler]
bot_name = "ClinicGrowthBot"
contact_url = "https://github.com/dasravik444-cpu/clinic-growth"

[runtime]
time_budget_minutes = 120
safety_margin_minutes = 6
use_curl_cffi = false
"""

CITY = """# {city} ({country}). Shared settings: _base.toml. Made by scripts/make_markets.py from config/cities.csv.
include = ["../shared/categories.toml", "_base.toml"]

[campaign]
id = "{code}-{slug}"
timezone = "{timezone}"
lead_id_prefix = "{prefix}"

[area]
name = "{city}"
aliases = [{aliases}]
center = [{lat}, {lon}]
radius_km = {radius_km}
"""


def main() -> None:
    with open(ROOT / "config" / "cities.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    done: dict[str, int] = {}
    for r in rows:
        cc, code = r["cc"].upper(), r["cc"].lower()
        if cc not in SUPPORTED:
            print(f"skipped {r['city']}: the lead finder has no rules for {cc} yet")
            continue
        out = ROOT / "config" / code
        out.mkdir(parents=True, exist_ok=True)
        if code not in done:
            (out / "_base.toml").write_text(BASE.format(country=r["country"], code=code, cc=cc,
                                                         region="uk" if cc == "GB" else code), encoding="utf-8")
        aliases = ", ".join(f'"{a.strip()}"' for a in r["aliases"].split("|") if a.strip())
        (out / f"{r['slug']}.toml").write_text(CITY.format(code=code, **{**r, "aliases": aliases}), encoding="utf-8")
        done[code] = done.get(code, 0) + 1
    for code, n in done.items():
        order = [r["slug"] for r in rows if r["cc"].lower() == code]
        lines = ["# The cities of this market in the order they are searched (one at a time, each until it is done).",
                 '# Put "#" in front of a line to leave a city out. New cities: config/cities.csv, then scripts/make_markets.py.',
                 "cities = ["] + [f'  "{s}",' for s in order] + ["]", ""]
        (ROOT / "config" / code / "fleet.toml").write_text("\n".join(lines), encoding="utf-8")
        print(f"{code}: {n} city files in config/{code}/")


if __name__ == "__main__":
    main()
