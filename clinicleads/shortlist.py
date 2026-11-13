"""Turn the lead finder's exports into the lists we work from.

  Clinics      practices we can pitch, best first, with the reasons for the score
  Consultants  clinics named after a doctor who is also listed on a hospital's site: confirm each, names repeat
  Rosters      the hospital-site doctor listings those matches came from (not leads: the phone is the hospital's)
  Hospitals    hospitals found (not leads)

Hospital doctors are recognised from the data itself: a website domain that carries several
doctor-named listings (a hospital group's "find a doctor" pages) is a roster domain.
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from urllib.parse import urlsplit

from . import crossmatch as cm
from .model import is_owner_named, norm_text, person_tokens

HIGH_VALUE = {"Dental clinic", "Skin / Hair / Cosmetic clinic", "Eye clinic", "Fertility / Women's clinic",
              "Orthopaedic / Physiotherapy clinic"}
# Sites that list many practices but belong to none of them: a lead whose only site is one of these has no site.
LISTING_SITES = ("practo.", "justdial.", "lybrate.", "sulekha.", "facebook.", "instagram.", "linkedin.", "google.",
                 "yelp.", "healthgrades.", "zocdoc.", "doctify.", "healthengine.", "hotdoc.", "wa.me", "linktr.ee",
                 "business.site", "indiamart.", "apollo247.", "1mg.", "credihealth.", "clinicspots.", "docindia.",
                 "nhs.uk", "webmd.", "vitals.", "ratemds.", "topdoctors.", "whatclinic.", "bookmydoctor.",
                 "eka.care", "share.google", "g.co/", "goo.gl", "bit.ly", "remedoapp.", "docon.", "healthplix.",
                 "clinicea.", "curofy.", "bajajfinservhealth.", "medibuddy.", "mfine.", "drlogy.", "wixsite.",
                 "blogspot.", "wordpress.com", "godaddysites.", "sites.google", "carrd.co", "youtube.", "x.com/",
                 "twitter.", "t.me/", "bestdoctorsin", "doctor-india", "dentist-india")
# Words that show a listing names a practice or a treatment, not a person.
NOT_A_NAME = set("""clinic clinics hospital hospitals dental dentist dentistry heart centre center care specialist
    specialists doctor doctors surgeon surgeons best top skin eye hair child children kids physiotherapy
    physiotherapist homeopathy homeopathic homeo ayurvedic ayurveda multispeciality speciality specialty super
    health healthcare medical nursing home polyclinic diagnostic diagnostics lab and the in of for at near
    consultant senior surgery orthopaedic orthopedic ortho gynecologist gynaecologist cardiologist dermatologist
    neurologist urologist pediatrician paediatrician physician ent ivf fertility laser cosmetic implant implants
    smile smiles kidney stone spine knee joint pain piles cancer diabetes thyroid treatment india indian
    delhi kolkata mumbai bangalore bengaluru chennai hyderabad london dubai singapore advanced family""".split())
ROSTER_MIN = 4          # doctor-named listings on one domain before it counts as a hospital roster
CLINIC_COLUMNS = ["Score", "Why", "City", "Country", "Review offer", "Business Name", "Category", "Owner-named",
                  "Phones", "Emails", "Website", "Facebook", "Instagram", "WhatsApp", "Area", "Address",
                  "Contact Rule", "Contact Sources", "Google Maps", "Lead ID"]
CONSULTANT_COLUMNS = ["Match", "Same field", "Hospital Doctor", "Listed on", "Roster Source"] + CLINIC_COLUMNS
ROSTER_COLUMNS = ["City", "Country", "Doctor", "Field", "Listed on", "Listing", "Listing page"]
HOSPITAL_COLUMNS = ["City", "Country", "Business Name", "Phones", "Emails", "Website", "Area", "Address"]


def domain(url: str) -> str:
    host = (urlsplit(url if "//" in url else "//" + url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def doctor_name(listing: str) -> str:
    """'Dr. Tapan Sinha - Best Cardiologist in Kolkata' -> 'Dr. Tapan Sinha'."""
    name = re.split(r"\s+[-|–:(]\s*|,|\bbest\b|[’']s\b", listing, maxsplit=1, flags=re.I)[0].strip()
    if not name:                                   # 'Best Cardiologist - Dr. Tapan Sinha'
        m = re.search(r"\b(dr\.?\s+[a-z][a-z .']+)", listing, re.I)
        name = m.group(1).strip() if m else ""
    kept = []
    for word in name.split():                      # 'Dr. Rashmi Sharma CONSULTANT DERMATOLOGY' stops at CONSULTANT
        if norm_text(word) in NOT_A_NAME:
            break
        kept.append(word)
    return " ".join(kept)


def is_person(listing: str) -> bool:
    parts = person_tokens(doctor_name(listing))
    return is_owner_named(listing) and 2 <= len(parts) <= 4 and len(parts[0]) >= 2 and not NOT_A_NAME & set(parts)


def roster_domains(rows: list[dict]) -> set[str]:
    """Domains that carry ROSTER_MIN or more different doctor-named listings."""
    seen: dict[str, set] = defaultdict(set)
    for r in rows:
        d = domain(r.get("Website", ""))
        if d and is_person(r.get("Business Name", "")):
            seen[d].add(" ".join(person_tokens(doctor_name(r["Business Name"]))))
    return {d for d, names in seen.items() if len(names) >= ROSTER_MIN and not any(x in d + "/" for x in LISTING_SITES)}


def own_site(url: str, rosters: set[str]) -> bool:
    d = domain(url)
    return bool(d) and d not in rosters and not any(x in d + "/" for x in LISTING_SITES)


def score(row: dict, rosters: set[str]) -> tuple[int, str]:
    pts, why = 0, []
    for cond, n, label in (
            (bool(row.get("Emails", "").strip()), 30, "e-mail"),
            (bool(row.get("Phones", "").strip()), 25, "phone"),
            (own_site(row.get("Website", ""), rosters), 15, "own website"),
            (is_owner_named(row.get("Business Name", "")), 15, "owner-named"),
            (row.get("Category") in HIGH_VALUE, 15, "high-value field")):
        if cond:
            pts += n
            why.append(label)
    return pts, ", ".join(why)


def build(exports: list[tuple[dict, list[dict]]]) -> dict[str, list[dict]]:
    """exports: (city row from config/cities.csv, that city's lead rows). Returns the four lists."""
    out = {"Clinics": [], "Consultants": [], "Rosters": [], "Hospitals": []}
    for city, rows in exports:
        tag = {"City": city["city"], "Country": city["country"], "Review offer": city.get("review_offer", "")}
        rosters = roster_domains(rows)
        roster, clinics = [], []
        for r in rows:
            r = {**r, **tag}
            if r.get("Category") == cm.HOSPITAL_LABEL:
                out["Hospitals"].append(r)
            elif domain(r.get("Website", "")) in rosters:          # a hospital's own listing: its phone, not a lead
                if not is_person(r.get("Business Name", "")):
                    continue
                roster.append({"doctor_name": doctor_name(r["Business Name"]), "specialty": r.get("Category", ""),
                               "hospital": domain(r["Website"]), "source_url": r["Website"], "listing": r["Business Name"]})
            else:
                pts, why = score(r, rosters)
                r.update({"Score": pts, "Why": why, "Owner-named": "yes" if is_owner_named(r["Business Name"]) else ""})
                clinics.append(r)
        out["Clinics"] += clinics
        out["Rosters"] += [{**tag, "Doctor": x["doctor_name"], "Field": x["specialty"], "Listed on": x["hospital"],
                            "Listing": x["listing"], "Listing page": x["source_url"]} for x in roster]
        # a hospital-site listing must not match itself, so only clinics with their own contact route are candidates
        named = [c for c in clinics if is_owner_named(c["Business Name"])
                 and (not c.get("Website", "").strip() or own_site(c["Website"], rosters))]
        field = {norm_text(x["doctor_name"]): x["specialty"] for x in roster}
        seen = set()
        for hit in cm.crossmatch([{**x, "hospital": ""} for x in roster], named):
            key = (norm_text(hit["Hospital Doctor"]), domain(hit.get("Website", "")) or hit.get("Phones", ""))
            if key in seen:                      # the same practice listed twice
                continue
            seen.add(key)
            hit.update({"Match": hit["Consultant Match"], "Listed on": domain(hit["Roster Source"]),
                        "Same field": "yes" if field.get(norm_text(hit["Hospital Doctor"])) == hit.get("Category") else ""})
            out["Consultants"].append(hit)
    out["Clinics"].sort(key=lambda r: -r["Score"])
    out["Consultants"].sort(key=lambda r: (r["Match"] != "strong", r["Same field"] != "yes", -r["Score"]))
    return out


def summary(lists: dict[str, list[dict]]) -> list[dict]:
    by_city: dict[str, Counter] = defaultdict(Counter)
    for r in lists["Clinics"]:
        c = by_city[r["City"]]
        c["Clinics"] += 1
        c["With phone"] += bool(r.get("Phones", "").strip())
        c["With e-mail"] += bool(r.get("Emails", "").strip())
        c["Owner-named"] += bool(r.get("Owner-named"))
        c["Score 70+"] += r["Score"] >= 70
    for key, name in (("Consultants", "Hospital doctors with own clinic"), ("Hospitals", "Hospitals"), ("Rosters", "Hospital-site doctor listings")):
        for r in lists[key]:
            by_city[r["City"]][name] += 1
    cols = ["Clinics", "With phone", "With e-mail", "Owner-named", "Score 70+", "Hospital doctors with own clinic",
            "Hospital-site doctor listings", "Hospitals"]
    rows = [{"City": city, **{k: c[k] for k in cols}} for city, c in by_city.items()]
    rows.append({"City": "TOTAL", **{k: sum(r[k] for r in rows) for k in cols}})
    return rows


def write_csv(rows: list[dict], path: str, columns: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_xlsx(lists: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    sheets = [("Summary", summary(lists), None), ("Clinics", lists["Clinics"], CLINIC_COLUMNS),
              ("Consultants", lists["Consultants"], CONSULTANT_COLUMNS), ("Rosters", lists["Rosters"], ROSTER_COLUMNS),
              ("Hospitals", lists["Hospitals"], HOSPITAL_COLUMNS)]
    for title, rows, cols in sheets:
        ws = wb.create_sheet(title)
        cols = cols or (list(rows[0].keys()) if rows else [])
        ws.append(cols)
        for r in rows:
            ws.append([r.get(c, "") for c in cols])
    wb.save(path)
