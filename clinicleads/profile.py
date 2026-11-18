"""The lead table the owner works from: one row per clinic, with the doctor, the speciality, the degrees the listing
shows, the hospital the doctor is also listed at, every contact route, and which of our services fit and why.

Everything comes from the listing itself or from rules written here; nothing is guessed about the person. Age is
not published in any of the sources we read, and degrees only when the clinic put them in its own name, so those
columns stay empty unless the data has them (the "Read me" sheet says how to look a doctor up by hand).
"""
from __future__ import annotations

import re

from . import shortlist as sl
from .model import norm_text

COLUMNS = ["Priority", "Lead ID", "Doctor", "Clinic / listing", "Speciality", "Degrees (as listed)",
           "Also listed at hospital", "City", "Area", "Address", "Phone", "Phone type", "WhatsApp", "E-mail",
           "Website", "Facebook", "Instagram", "Services that fit (our suggestion)", "Why these", "Extra",
           "Google Maps", "Where the contacts came from", "Key"]
READ_ME = [
    ("What this is", "Every clinic found for these cities, best first. One row per clinic."),
    ("Priority", "High: a hospital doctor with an own clinic, or a strong lead with e-mail. Medium: has e-mail. "
                 "Low: phone only. The e-mail robot writes to High first."),
    ("Doctor", "Filled when the clinic is named after a doctor (\"Dr. Anita Rao ...\"). Otherwise the listing does "
               "not say who the doctor is: ask on the phone."),
    ("Speciality", "From the listing's own name (\"... Best Cardiologist\") or its map category."),
    ("Degrees (as listed)", "Only when the clinic wrote them into its own name (\"Dr X, MBBS, MD\"). Few do. To "
                            "check a doctor's degrees and the year they qualified, search their name on the "
                            "National Medical Commission's Indian Medical Register (nmc.org.in), by hand."),
    ("Approx. age", "Not in this table: no public source we read gives it. The year of the first degree on the "
                    "medical register (above) is the nearest honest guide (most qualify at about 23-24)."),
    ("Also listed at hospital", "The doctor's name also appears on that hospital group's own website (Apollo, "
                                "Fortis, Max ...). A name match, not a confirmation: two doctors can share a name."),
    ("Phone type", "Mobile or landline, from the number itself. A mobile number may be on WhatsApp; that is not "
                   "confirmed. WhatsApp shows a number only where the clinic published one as WhatsApp."),
    ("Services that fit", "Our suggestion from the speciality and the listing, for your call: the receptionist and "
                          "reminders fit every clinic; the rest depends on the kind of practice."),
    ("Status", "Write call results in the Google Sheet's Status column, not here: anything typed there stops "
               "the robot's e-mails to that clinic."),
]

# (words in the listing, the speciality shown). The first that matches wins, so narrower names come first.
SPECIALITIES = [
    (("orthodont", "braces", "aligner"), "Orthodontics"),
    (("implant",), "Dental implants"),
    (("dental", "dentist", "dentistry", "endodont", "periodont", "prosthodont", "tooth", "teeth", "root canal",
      "smile"), "Dentistry"),
    (("ivf", "fertility", "infertility", "test tube"), "Fertility (IVF)"),
    (("gynae", "gynec", "gyneco", "gynaeco", "obstet", "maternity", "women"), "Obstetrics & gynaecology"),
    (("cardio", "heart"), "Cardiology"),
    (("paediatric", "pediatric", "child", "children", "kids", "neonat"), "Paediatrics"),
    (("physio", "rehab", "chiropract"), "Physiotherapy"),
    (("orthop", "ortho ", "spine", "knee", "joint", "bone", "sports injur"), "Orthopaedics"),
    (("derma", "skin", "cosmet", "aesthetic", "hair", "laser", "trichol"), "Dermatology & cosmetic"),
    (("ophthal", "eye", "lasik", "retina", "cataract", "vision", "netralaya"), "Ophthalmology"),
    ((" ent ", "ent clinic", "ear nose", "otorhino", "hearing"), "ENT"),
    (("neuro", "brain"), "Neurology"),
    (("urolog", "kidney stone", "andrology"), "Urology"),
    (("nephro", "kidney", "dialysis"), "Nephrology"),
    (("gastro", "liver", "hepat", "endoscop"), "Gastroenterology"),
    (("diabet", "endocrin", "thyroid", "obesity"), "Diabetes & endocrinology"),
    (("psychiat", "mental", "psycholog", "counsel", "de-addiction"), "Psychiatry & mental health"),
    (("pulmo", "chest", "asthma", "lung", "respir"), "Pulmonology"),
    (("onco", "cancer"), "Oncology"),
    (("piles", "fistula", "proctolog", "laparoscop", "surgeon", "surgery"), "Surgery"),
    (("homoeo", "homeo"), "Homeopathy"),
    (("ayurved", "ayush", "panchakarma"), "Ayurveda"),
    (("physician", "general", "family", "medicine", "polyclinic", "medical centre", "medical center"),
     "General medicine"),
]
CATEGORY_SPECIALITY = {"Dental clinic": "Dentistry", "Skin / Hair / Cosmetic clinic": "Dermatology & cosmetic",
                       "Eye clinic": "Ophthalmology", "Fertility / Women's clinic": "Obstetrics & gynaecology",
                       "Orthopaedic / Physiotherapy clinic": "Orthopaedics", "Doctor's clinic": "",
                       "Clinic / Polyclinic": "General medicine"}
DEGREES = re.compile(r"\b(MBBS|M\.B\.B\.S|BDS|MDS|MD|M\.D|MS|M\.S|DNB|DM|MCh|M\.Ch|FRCS|MRCP|MRCOG|DGO|DCH|DDVL|DVD|"
                     r"DLO|DOMS|DO|BPT|MPT|BAMS|BHMS|BUMS|FCPS|FICS|FACS|FIAGES|PhD|MPH|FRCP|FRCOG|DPM)\b\.?")

SERVICES = {
    "receptionist": "Receptionist 24/7",
    "reminders": "Appointment reminders",
    "followups": "Follow-ups the doctor advises",
    "rebook": "Missed visits rebooked",
    "postvisit": "Post-visit check",
    "feedback": "Private patient feedback",
    "sheet": "Morning sheet",
    "website": "Website",
}
# Specialities whose patients come back on the doctor's advice (sittings, courses, reviews, recalls).
FOLLOW_UP = {"Orthodontics", "Dental implants", "Dentistry", "Fertility (IVF)", "Obstetrics & gynaecology",
             "Cardiology", "Paediatrics", "Physiotherapy", "Orthopaedics", "Dermatology & cosmetic", "Ophthalmology",
             "Diabetes & endocrinology", "Nephrology", "Oncology", "Psychiatry & mental health", "ENT", "Urology",
             "Gastroenterology", "Pulmonology", "Neurology", "Surgery"}
# Treatments spread over several visits, where a missed one breaks the plan.
MULTI_VISIT = {"Orthodontics", "Dental implants", "Dentistry", "Physiotherapy", "Dermatology & cosmetic",
               "Fertility (IVF)"}
# Procedures after which a check the next day is kind and catches problems early.
PROCEDURES = {"Dental implants", "Dentistry", "Ophthalmology", "Dermatology & cosmetic", "Orthopaedics", "Surgery",
              "Fertility (IVF)", "Obstetrics & gynaecology", "Urology"}
WHY = {
    "Orthodontics": "monthly brace adjustments", "Dental implants": "implants need several sittings",
    "Dentistry": "next sittings and six-month checks", "Fertility (IVF)": "visits on exact cycle days",
    "Obstetrics & gynaecology": "antenatal check-ups on a schedule", "Cardiology": "regular reviews and tests",
    "Paediatrics": "vaccination and growth visits", "Physiotherapy": "treatment plans of many sessions",
    "Orthopaedics": "post-fracture and post-surgery reviews", "Dermatology & cosmetic": "courses of sittings",
    "Ophthalmology": "post-operative and yearly eye checks", "Diabetes & endocrinology": "three-monthly reviews",
}


def speciality(name: str, category: str) -> str:
    text = f" {norm_text(name)} "
    for words, label in SPECIALITIES:
        if any(f" {w.strip()}" in text if w.startswith(" ") else w in text for w in words):
            return label
    return CATEGORY_SPECIALITY.get(category, "")


def degrees(name: str) -> str:
    found = []
    for m in DEGREES.finditer(name or ""):
        d = m.group(1).replace(".", "")
        d = {"MCh": "MCh", "MBBS": "MBBS"}.get(d, d)
        if d not in found:
            found.append(d)
    return ", ".join(found)


def phone_type(phone: str) -> str:
    line = (phone or "").split("\n")[0].strip()
    first, _, label = line.partition("(")
    first, label = first.strip(), label.rstrip(")").strip().lower()
    if not first:
        return ""
    if label.startswith("mobile/landline") or label.startswith("landline/mobile"):
        return "Mobile or landline"
    if label.startswith("mobile"):
        return "Mobile (may be on WhatsApp)"
    if label.startswith("landline") or label.startswith("fixed"):
        return "Landline"
    try:
        import phonenumbers

        n = phonenumbers.parse(first, "IN")
        t = phonenumbers.number_type(n)
    except Exception:  # noqa: BLE001 - an odd number is still shown, just without a type
        return ""
    from phonenumbers import PhoneNumberType as P

    if t == P.MOBILE:
        return "Mobile (may be on WhatsApp)"
    if t == P.FIXED_LINE:
        return "Landline"
    if t == P.FIXED_LINE_OR_MOBILE:
        return "Mobile or landline"
    return ""


def services(spec: str, *, hospital: bool, own_site: bool, has_mail: bool) -> tuple[list[str], str]:
    """Our suggestion of which services fit this clinic, and why, in a sentence for the call."""
    pick = ["receptionist", "reminders"]
    why = []
    if hospital:
        why.append("also works at a hospital: nobody answers the clinic phone while the doctor is there")
    else:
        why.append("every missed call can go to another clinic")
    if spec in FOLLOW_UP:
        pick.append("followups")
        if spec in WHY:
            why.append(f"{spec.lower()} means {WHY[spec]}")
    if spec in MULTI_VISIT:
        pick.append("rebook")
    if spec in PROCEDURES:
        pick.append("postvisit")
    if hospital:
        pick.append("sheet")
    if not own_site:
        pick.append("website")
        why.append("no website of its own")
    pick.append("feedback")
    return [SERVICES[p] for p in pick], "; ".join(why).capitalize() + "."


def rows_for(exports: list[tuple[dict, list[dict]]]) -> list[dict]:
    """The table for these cities (city row from config/cities.csv, that city's lead finder export), best first."""
    out = []
    for city, leads in exports:
        lists = sl.build([(city, leads)])
        rosters = sl.roster_domains(leads)
        consult = {h["Key"]: h for h in lists["Consultants"]}
        for r in lists["Clinics"]:
            name = r.get("Business Name", "")
            hit = consult.get(r.get("Key"))
            doctor = hit["Hospital Doctor"] if hit else ""
            if not doctor:
                from clinicreach.outreach.templates import doctor_of

                doctor = doctor_of(name)
            has_mail = bool(r.get("Emails", "").strip())
            own = sl.own_site(r.get("Website", ""), rosters)
            spec = speciality(name, r.get("Category", ""))
            if hit and hit.get("Hospital Specialty") and not spec:
                spec = CATEGORY_SPECIALITY.get(hit["Hospital Specialty"], "")
            fits, why = services(spec, hospital=bool(hit), own_site=own, has_mail=has_mail)
            if hit and hit["Match"] == "strong":
                priority = "High"
            elif has_mail and r["Score"] >= 85:
                priority = "High"
            else:
                priority = "Medium" if has_mail else "Low"
            extra = []
            if hit:
                extra.append(f"{hit['Match']} name match with a doctor on {hit['Listed on']}: confirm before calling "
                             f"it a hospital connection")
            if not r.get("Phones", "").strip():
                extra.append("no phone published")
            if r.get("Website") and not own:
                extra.append(f"its only web page is a listing ({sl.domain(r['Website'])})")
            out.append({
                "Priority": priority, "Lead ID": r.get("Lead ID", ""), "Doctor": doctor, "Clinic / listing": name,
                "Speciality": spec or "Not stated", "Degrees (as listed)": degrees(name),
                "Also listed at hospital": hit["Listed on"] if hit else "", "City": city["city"],
                "Area": r.get("Area", ""), "Address": r.get("Address", ""), "Phone": r.get("Phones", ""),
                "Phone type": phone_type(r.get("Phones", "")), "WhatsApp": r.get("WhatsApp", ""),
                "E-mail": r.get("Emails", ""), "Website": r.get("Website", "") if own else "",
                "Facebook": r.get("Facebook", ""), "Instagram": r.get("Instagram", ""),
                "Services that fit (our suggestion)": ", ".join(fits), "Why these": why, "Extra": "; ".join(extra),
                "Google Maps": r.get("Google Maps", ""), "Where the contacts came from": r.get("Contact Sources", ""),
                "Key": r.get("Key", ""), "_score": r["Score"]})
    rank = {"High": 0, "Medium": 1, "Low": 2}
    out.sort(key=lambda x: (rank[x["Priority"]], -x["_score"], not x["Doctor"]))
    return out


def write_xlsx(rows: list[dict], path: str, title: str) -> int:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    info = wb.active
    info.title = "Read me"
    info.append([title])
    info["A1"].font = Font(bold=True, size=13)
    info.append([])
    for k, v in READ_ME:
        info.append([k, v])
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 110
    for row in info.iter_rows(min_row=3):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws = wb.create_sheet("Clinics")
    ws.append(COLUMNS)
    for r in rows:
        ws.append([r.get(c, "") for c in COLUMNS])
    head = PatternFill("solid", fgColor="13294B")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head
    widths = {"Priority": 9, "Lead ID": 11, "Doctor": 24, "Clinic / listing": 34, "Speciality": 22,
              "Degrees (as listed)": 14, "Also listed at hospital": 22, "City": 12, "Area": 16, "Address": 34,
              "Phone": 18, "Phone type": 22, "WhatsApp": 14, "E-mail": 28, "Website": 28, "Facebook": 22,
              "Instagram": 18, "Services that fit (our suggestion)": 46, "Why these": 60, "Extra": 40,
              "Google Maps": 20, "Where the contacts came from": 30, "Key": 14}
    from openpyxl.utils import get_column_letter

    for i, c in enumerate(COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(c, 16)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rows) + 1}"
    wb.save(path)
    return len(rows)
