"""Offline tests of the clinic layer. Every place and person here is invented."""
import csv
import glob
import os

from clinicleads import crossmatch as cm
from clinicleads import npi
from clinicleads.cli import city_config, paths
from clinicleads.model import is_owner_named, person_tokens
from leadgen.config import load_config
from leadgen.db import DB
from leadgen.providers.overture import OvertureStore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KOLKATA = (22.5726, 88.3639)


def test_every_city_in_the_list_has_a_config_that_loads():
    with open(os.path.join(ROOT, "config", "cities.csv"), newline="") as f:
        cities = list(csv.DictReader(f))
    assert len(cities) == 27 and len({c["slug"] for c in cities}) == 27
    for c in cities:
        assert c["review_offer"] in ("restricted", "allowed-with-rules", "check")
        cfg = load_config(city_config(c["slug"]))
        assert cfg["campaign"]["country"] == c["cc"]
        assert cfg["area"]["center"] == [float(c["lat"]), float(c["lon"])]
        assert cfg["crawler"]["bot_name"] == "ClinicGrowthBot"
        assert cfg["compliance"]["mode"] == "open-data"
        assert [k["key"] for k in cfg["categories"]][-1] == "hospital"
    files = [p for p in glob.glob(os.path.join(ROOT, "config", "??", "*.toml"))
             if os.path.basename(p) not in ("_base.toml", "fleet.toml")]
    assert len(files) == 27


def test_each_city_keeps_its_own_database_and_export():
    cfg, db, out = paths("new-delhi")
    assert cfg.endswith("config/in/new-delhi.toml")
    assert db.endswith("state/in-new-delhi.sqlite") and out.endswith("data/leads-new-delhi.csv")


def place(i, name, code, dlat=0.0, **kw):
    return {"id": f"08f{i:013d}", "name": name, "lat": KOLKATA[0] + dlat, "lng": KOLKATA[1], "code": code,
            "basic": kw.get("basic", code), "alternates": [], "phones": kw.get("phones", [f"+91 98300 1{i:04d}"]),
            "emails": [], "websites": [], "socials": [], "street": f"{i} Test Road", "locality": "Salt Lake",
            "postcode": "700091", "confidence": 0.8, "brand": kw.get("brand"), "status": None, "datasets": ["meta"]}


def test_medical_categories_pick_practices_and_drop_the_rest(tmp_path):
    cfg = load_config(city_config("kolkata"))
    rows = [place(1, "Dr Testwala's Dental Care", "general_dentistry", basic="dental_clinic"),
            place(2, "Fictionrao Skin Clinic", "dermatology", dlat=0.002, basic="specialized_health_care"),
            place(3, "Sample General Hospital", "hospital", dlat=0.004),
            place(4, "Corner Pharmacy", "pharmacy", dlat=0.006),
            place(5, "Clove Dental Sample Nagar", "dental_clinic", dlat=0.008)]
    st = OvertureStore(DB(str(tmp_path / "s.sqlite")), cfg, fetcher=lambda *a: [dict(r) for r in rows],
                       release_fn=lambda: "2026-09-23.1")
    assert st.category_for("dental_clinic", "dental_clinic", "Any Dental") == "dental"
    assert st.category_for("orthodontics", "dental_clinic", "Brace Place") == "dental"
    assert st.category_for("dermatology", "specialized_health_care", "Skin Clinic") == "skin"
    assert st.category_for("optometry", "vision_or_eye_care_clinic", "Specs Shop") is None
    assert st.category_for("doctors_office", "diagnostics_imaging_or_lab_service", "Dr X") == "doctor"
    assert st.category_for("diagnostic_imaging", "diagnostics_imaging_or_lab_service", "Scan Centre") is None
    assert st.category_for("hospital", "hospital", "City Hospital") == "hospital"
    assert st.category_for("pharmacy", "pharmacy", "Corner Pharmacy") is None
    found = {c: {p.name for p in st.search_cell(KOLKATA[0], KOLKATA[1], 3.0, c)} for c in ("dental", "skin", "hospital")}
    assert "Dr Testwala's Dental Care" in found["dental"]
    assert found["skin"] == {"Fictionrao Skin Clinic"}
    assert found["hospital"] == {"Sample General Hospital"}


def test_name_helpers():
    assert is_owner_named("Dr. Mehta's Clinic") and not is_owner_named("Drishti Eye Centre")
    assert person_tokens("Prof. Dr. Anita K. Rao, MBBS, MD") == ["anita", "k", "rao"]


def test_match_strength():
    assert cm.match_strength("Dr Anita Fictionrao", "Anita Fictionrao Skin Clinic") == "strong"
    assert cm.match_strength("Dr Anita Fictionrao", "Dr A Fictionrao Clinic") == "weak"
    assert cm.match_strength("Dr Raj Kumar", "Dr R Kumar Clinic") == ""          # common surname
    assert cm.match_strength("Dr Anita Fictionrao", "Fictionrao Nagar Clinic") == ""
    assert cm.match_strength("Madonna", "Madonna Clinic") == ""


LEADS = [
    {"Business Name": "Anita Fictionrao Skin Clinic", "Category": "Skin / Hair / Cosmetic clinic", "Phones": "1"},
    {"Business Name": "Sunrise Dental", "Category": "Dental clinic", "Contact Person": "Dr V Inventedkar"},
    {"Business Name": "Sample General Hospital", "Category": cm.HOSPITAL_LABEL, "Website": "https://sgh.example"},
    {"Business Name": "Sample General Hospital - Dr Anita Fictionrao OPD", "Category": "Doctor's clinic"},
    {"Business Name": "City Family Physicians", "Category": "Doctor's clinic"},
]
ROSTER = [
    {"doctor_name": "Dr. Anita Fictionrao, MD", "specialty": "Dermatology", "hospital": "Sample General Hospital",
     "source_url": "https://sgh.example/doctors"},
    {"doctor_name": "Dr. Vikram Inventedkar", "specialty": "Dental Surgery", "hospital": "Sample General Hospital",
     "source_url": "https://sgh.example/doctors"},
    {"doctor_name": "Dr. Raj Kumar", "specialty": "Medicine", "hospital": "Sample General Hospital", "source_url": ""},
]


def test_crossmatch_finds_private_practices_only(tmp_path):
    hits = cm.crossmatch(ROSTER, LEADS)
    assert [(h["Business Name"], h["Consultant Match"]) for h in hits] == [
        ("Anita Fictionrao Skin Clinic", "strong"), ("Sunrise Dental", "weak")]
    assert hits[0]["Hospital"] == "Sample General Hospital" and hits[0]["Roster Source"].endswith("/doctors")
    assert [h["Business Name"] for h in cm.hospitals(LEADS)] == ["Sample General Hospital"]
    out = tmp_path / "c.csv"
    assert cm.write_csv(hits, str(out), cm.EXTRA_COLUMNS + ["Business Name", "Phones"]) == 2
    assert cm.read_csv(str(out))[0]["Hospital Doctor"] == "Dr. Anita Fictionrao, MD"


def test_roster_file_round_trip(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("doctor_name,specialty,hospital,source_url\nDr A B,Skin,H,u\n,,,\n", encoding="utf-8")
    assert len(cm.load_roster(str(p))) == 1


NPI_PAYLOAD = {"result_count": 3, "results": [
    {"number": 1000000001, "basic": {"first_name": "PAT", "last_name": "SAMPLE", "status": "A"},
     "addresses": [{"address_purpose": "MAILING", "address_1": "PO BOX 1"},
                   {"address_purpose": "LOCATION", "address_1": "100 TEST ST NW", "city": "WASHINGTON",
                    "state": "DC", "postal_code": "200010000", "telephone_number": "202-555-0100"}],
     "practiceLocations": [{"address_1": "5 OTHER AVE"}], "taxonomies": [{"desc": "Dentist", "primary": True}]},
    {"number": 1000000002, "basic": {"first_name": "LEE", "last_name": "DEMO", "status": "A"},
     "addresses": [{"address_purpose": "LOCATION", "address_1": "1 UNIVERSITY HOSPITAL DR", "city": "WASHINGTON",
                    "state": "DC", "postal_code": "20002"}],
     "practiceLocations": [{"address_1": "x"}], "taxonomies": [{"desc": "Dermatology"}]},
    {"number": 1000000003, "basic": {"first_name": "X", "last_name": "GONE", "status": "D"},
     "addresses": [{"address_purpose": "LOCATION", "address_1": "1 A ST"}], "taxonomies": []},
]}


def test_npi_parse_and_paging(monkeypatch):
    a, b = npi.parse(NPI_PAYLOAD, "Dentist")                      # the deactivated record is dropped
    assert (a["Name"], a["Phone"], a["Own Practice Signal"]) == ("Dr. Pat Sample", "202-555-0100", "yes")
    assert a["Address"] == "100 Test St Nw, Washington, DC, 20001"
    assert b["Own Practice Signal"] == ""                         # main address is a hospital
    calls = []
    monkeypatch.setattr(npi, "fetch_json", lambda url, **k: calls.append(url) or NPI_PAYLOAD)
    rows = npi.collect("Washington", "DC", taxonomies=["Dentist", "Dermatology"], pause=0)
    assert len(calls) == 2 and len(rows) == 2                     # same clinicians under two searches: kept once
    assert "taxonomy_description=Dentist" in calls[0] and "state=DC" in calls[0]


# ---- shortlist: scoring, hospital rosters found in the data, consultants ------------------------
from clinicleads import shortlist as sl  # noqa: E402

CITY = {"city": "Kolkata", "country": "India", "review_offer": "restricted"}


def lead(name, category="Doctor's clinic", website="", phones="+91 98300 00100", emails=""):
    return {"Business Name": name, "Category": category, "Website": website, "Phones": phones, "Emails": emails,
            "Lead ID": name[:6]}


SHORT = (
    [lead(f"Dr. {n} - Best Cardiologist", website=f"https://www.bighospital.example/doctors/{i}")
     for i, n in enumerate(["Anita Fictionrao", "Vikram Inventedkar", "Rina Madeupta", "Sunil Notrealson"])]
    + [lead("Dr Anita Fictionrao Heart Clinic", website="https://dranita.example", emails="a@dranita.example"),
       lead("Dr. Anita Fictionrao", website="https://dranita.example"),                    # the same practice again
       lead("Dr. V Inventedkar Dental Care", "Dental clinic"),
       lead("City Smiles", "Dental clinic", website="https://www.facebook.com/citysmiles", emails="c@x.example"),
       lead("No Contact Clinic", phones=""),
       lead("Big Hospital", cm.HOSPITAL_LABEL, website="https://www.bighospital.example")]
)


def test_doctor_names_and_domains():
    assert sl.doctor_name("Dr. Tapan Sinha - Best Cardiologist in Kolkata") == "Dr. Tapan Sinha"
    assert sl.doctor_name("Dr Atul Shrivastava, Knee and Shoulder Surgeon") == "Dr Atul Shrivastava"
    assert sl.doctor_name("Best Medical Genetics Doctor - Dr. Saswati M") == "Dr. Saswati M"
    assert sl.is_person("Dr. Tapan Sinha")
    assert not sl.is_person("City Smiles Dental")
    assert not sl.is_person("Dr Sanjiv's Epione Heart Clinic") and not sl.is_person("Kidney Stone Specialist Doctor in Delhi")
    assert sl.doctor_name("Dr Sanjiv's Epione Heart Clinic") == "Dr Sanjiv"
    assert sl.doctor_name("Dr. Rashmi Sharma CONSULTANT DERMATOLOGY | Fortis") == "Dr. Rashmi Sharma"
    assert not sl.is_person("Dr Smile Dental Clinic") and not sl.is_person("Dr. Tooth Dental Studio")
    assert cm.match_strength("Dr Sanjiv Fictionrao", "Dr. Kiran's Fictionrao Clinic") == ""       # 's is not an initial
    profiles = [lead(f"Dr. {n}", website=f"https://www.eka.care/doctor/{i}") for i, n in enumerate(["A Bee", "Cee Dee", "Eff Gee", "Aitch Eye"])]
    assert sl.roster_domains(profiles) == set()                                                    # a profile site, not a hospital
    assert sl.domain("https://www.BigHospital.example/doctors/1") == "bighospital.example"
    assert sl.roster_domains(SHORT) == {"bighospital.example"}
    assert sl.own_site("https://dranita.example", {"bighospital.example"})
    assert not sl.own_site("https://www.facebook.com/citysmiles", set())
    assert not sl.own_site("https://www.bighospital.example/doctors/1", {"bighospital.example"})


def test_shortlist_splits_scores_and_matches(tmp_path):
    lists = sl.build([(CITY, SHORT)])
    assert {k: len(v) for k, v in lists.items()} == {"Clinics": 5, "Consultants": 2, "Rosters": 4, "Hospitals": 1}
    top = lists["Clinics"][0]
    assert (top["Business Name"], top["Score"]) == ("Dr Anita Fictionrao Heart Clinic", 85)
    assert top["Why"] == "e-mail, phone, own website, owner-named" and top["Review offer"] == "restricted"
    by = {r["Business Name"]: r for r in lists["Clinics"]}
    assert by["City Smiles"]["Score"] == 70                 # e-mail + phone + high-value field; Facebook is not a site
    assert by["No Contact Clinic"]["Score"] == 0
    strong, weak = lists["Consultants"]
    assert (strong["Match"], strong["Hospital Doctor"], strong["Listed on"]) == ("strong", "Dr. Anita Fictionrao", "bighospital.example")
    assert strong["Same field"] == "yes"
    assert (weak["Match"], weak["Business Name"], weak["Same field"]) == ("weak", "Dr. V Inventedkar Dental Care", "")
    total = sl.summary(lists)[-1]
    assert (total["City"], total["Clinics"], total["With e-mail"], total["Hospital doctors with own clinic"]) == ("TOTAL", 5, 2, 2)
    out = tmp_path / "l.xlsx"
    sl.write_xlsx(lists, str(out))
    from openpyxl import load_workbook
    wb = load_workbook(str(out))
    assert wb.sheetnames == ["Summary", "Clinics", "Consultants", "Rosters", "Hospitals"]
    assert wb["Clinics"].max_row == 6 and wb["Clinics"]["A1"].value == "Score"
