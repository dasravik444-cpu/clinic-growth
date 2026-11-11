"""Offline tests. Every place and person here is invented."""
import json
import os
import tempfile
import unittest

from clinicleads import crossmatch as cm
from clinicleads import enrich, npi, overpass, store
from clinicleads.cli import load_cities, main
from clinicleads.model import Lead, is_chain, is_owner_named, person_tokens, score
from clinicleads.net import FetchError

HERE = os.path.dirname(__file__)
DELHI = {"city": "New Delhi", "country": "India", "cc": "IN", "lat": "28.6139",
         "lon": "77.2090", "radius_km": "25", "review_offer": "restricted"}


def sample():
    with open(os.path.join(HERE, "fixtures", "overpass_sample.json")) as f:
        return overpass.parse(json.load(f), DELHI, "2026-01-01T00:00:00Z")


class Overpass(unittest.TestCase):
    def test_query_shape(self):
        q = overpass.build_query(28.6139, 77.209, 25)
        self.assertIn("(around:25000,28.6139,77.209)", q)
        self.assertTrue(q.startswith("[out:json]") and q.endswith("out center tags;"))
        self.assertEqual(q.count("("), q.count(")"))

    def test_parse_skips_unnamed_and_reads_tags(self):
        leads = sample()
        self.assertEqual(len(leads), 6)                     # the unnamed node is dropped
        d = leads[0]
        self.assertEqual((d.kind, d.phone, d.address), ("dentist", "+91 11 5550 0101", "12 Sample Marg, New Delhi"))
        self.assertEqual(d.source_url, "https://www.openstreetmap.org/node/1001")
        skin = next(l for l in leads if l.source_id == "way/2001")
        self.assertEqual((skin.lat, skin.email, skin.specialty), (28.64, "hello@fictionrao.example", "dermatology"))
        self.assertEqual(next(l for l in leads if "Hospital" in l.name).kind, "hospital")
        self.assertEqual(d.review_offer, "restricted")

    def test_falls_back_to_next_server(self):
        calls = []

        def fake(url, data=None, **kw):
            calls.append(url)
            if len(calls) == 1:
                raise FetchError("down")
            return {"elements": []}
        orig, overpass.fetch_json = overpass.fetch_json, fake
        try:
            self.assertEqual(overpass.collect(DELHI, endpoints=["a", "b"]), [])
            with self.assertRaises(FetchError):
                calls.clear()
                overpass.fetch_json = lambda *a, **k: (_ for _ in ()).throw(FetchError("down"))
                overpass.collect(DELHI, endpoints=["a", "b"])
        finally:
            overpass.fetch_json = orig


class Scoring(unittest.TestCase):
    def test_names(self):
        self.assertTrue(is_owner_named("Dr. Mehta's Clinic"))
        self.assertFalse(is_owner_named("Drishti Eye Centre"))
        self.assertTrue(is_chain("Apollo Clinic Saket"))
        self.assertFalse(is_chain("Appollonia Dental"))
        self.assertEqual(person_tokens("Prof. Dr. Anita K. Rao, MBBS, MD"), ["anita", "k", "rao"])

    def test_score_orders_sensibly(self):
        leads = {l.source_id: score(l) for l in sample()}
        dentist, chain, hospital = leads["node/1001"], leads["node/1003"], leads["way/2002"]
        self.assertGreater(dentist.score, chain.score)
        self.assertEqual(hospital.score, 0)
        self.assertIn("owner-named", dentist.score_reasons)
        self.assertIn("high-value", dentist.score_reasons)
        self.assertIn("chain", chain.score_reasons)
        plain = score(Lead("t", "1", name="President Student Residency Clinic"))
        self.assertNotIn("high-value", plain.score_reasons)   # 'dent' inside a word is not dental
        self.assertIn("high-value", score(Lead("t", "2", name="City ENT Centre", phone="1")).score_reasons)


class Store(unittest.TestCase):
    def test_dedupe_keeps_richer_copy(self):
        kept = store.dedupe(sample())
        same = [l for l in kept if "Testwala" in l.name]
        self.assertEqual(len(same), 1)
        self.assertTrue(same[0].phone)

    def test_same_name_far_apart_is_kept(self):
        a = Lead("osm", "n/1", name="Smile Dental", cc="IN", lat=28.60, lon=77.20)
        b = Lead("osm", "n/2", name="Smile Dental", cc="IN", lat=28.70, lon=77.30)
        self.assertEqual(len(store.dedupe([a, b])), 2)

    def test_save_load_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = store.connect(os.path.join(tmp, "t.sqlite"))
            store.save(db, store.dedupe(sample()))
            store.save(db, store.dedupe(sample()))                 # second run must not duplicate
            leads = store.load(db, "kind != 'hospital'")
            self.assertEqual(len(leads), 4)
            for ext in ("csv", "xlsx"):
                out = os.path.join(tmp, f"o.{ext}")
                self.assertEqual(store.export(leads, out), 4)
                self.assertGreater(os.path.getsize(out), 100)
            with open(os.path.join(tmp, "o.csv")) as f:
                first = f.readlines()[1]
            self.assertIn("Testwala", first)                       # best lead first


class Crossmatch(unittest.TestCase):
    ROSTER = [
        {"doctor_name": "Dr. Anita Fictionrao, MD", "specialty": "Dermatology",
         "hospital": "Sample General Hospital", "city": "New Delhi", "source_url": "https://sgh.example/doctors"},
        {"doctor_name": "Dr. Raj Kumar", "specialty": "Medicine",
         "hospital": "Sample General Hospital", "city": "New Delhi", "source_url": ""},
    ]

    def test_strength(self):
        self.assertEqual(cm.match_strength("Dr Anita Fictionrao", "Anita Fictionrao Skin Clinic"), "strong")
        self.assertEqual(cm.match_strength("Dr Anita Fictionrao", "Dr A Fictionrao Clinic"), "weak")
        self.assertEqual(cm.match_strength("Dr Raj Kumar", "Dr R Kumar Clinic"), "")      # common surname
        self.assertEqual(cm.match_strength("Dr Anita Fictionrao", "Fictionrao Nagar Clinic"), "")
        self.assertEqual(cm.match_strength("Madonna", "Madonna Clinic"), "")

    def test_apply_marks_only_private_clinic(self):
        leads = sample()
        self.assertEqual(cm.apply(self.ROSTER, leads), 1)
        hit = next(l for l in leads if l.consultant_match)
        self.assertEqual(hit.source_id, "way/2001")
        self.assertIn("Sample General Hospital", hit.consultant_match)
        self.assertIn("hospital consultant", score(hit).score_reasons)

    def test_other_city_and_hospital_department_ignored(self):
        other = [dict(self.ROSTER[0], city="Mumbai")]
        self.assertEqual(cm.apply(other, sample()), 0)
        dept = Lead("osm", "n/9", name="Sample General Hospital - Dr Anita Fictionrao OPD", city="New Delhi")
        self.assertEqual(cm.crossmatch(self.ROSTER, [dept]), [])


class Npi(unittest.TestCase):
    PAYLOAD = {"result_count": 3, "results": [
        {"number": 1000000001, "basic": {"first_name": "PAT", "last_name": "SAMPLE", "status": "A"},
         "addresses": [{"address_purpose": "MAILING", "address_1": "PO BOX 1"},
                       {"address_purpose": "LOCATION", "address_1": "100 TEST ST NW", "city": "WASHINGTON",
                        "state": "DC", "postal_code": "200010000", "telephone_number": "202-555-0100"}],
         "practiceLocations": [{"address_1": "5 OTHER AVE"}],
         "taxonomies": [{"desc": "Dentist", "primary": True}]},
        {"number": 1000000002, "basic": {"first_name": "LEE", "last_name": "DEMO", "status": "A"},
         "addresses": [{"address_purpose": "LOCATION", "address_1": "1 UNIVERSITY HOSPITAL DR",
                        "city": "WASHINGTON", "state": "DC", "postal_code": "20002"}],
         "practiceLocations": [{"address_1": "x"}], "taxonomies": [{"desc": "Dermatology"}]},
        {"number": 1000000003, "basic": {"first_name": "X", "last_name": "GONE", "status": "D"},
         "addresses": [{"address_purpose": "LOCATION", "address_1": "1 A ST"}], "taxonomies": []},
    ]}

    def test_parse(self):
        city = {"city": "Washington", "country": "United States", "cc": "US"}
        leads = npi.parse(self.PAYLOAD, city, "Dentist", "2026-01-01T00:00:00Z")
        self.assertEqual(len(leads), 2)                              # deactivated record dropped
        a, b = leads
        self.assertEqual((a.name, a.phone), ("Dr. Pat Sample", "202-555-0100"))
        self.assertEqual(a.address, "100 Test St Nw, Washington, DC, 20001")
        self.assertIn("2 practice locations", a.consultant_match)
        self.assertEqual(b.consultant_match, "")                      # main address is a hospital


class Enrich(unittest.TestCase):
    HOME = ('<a href="/contact-us">Contact</a> <a href="https://other.example/contact">x</a>'
            '<img src="logo@2x.png"> <a href="tel:+91%2011%205550%200101">call</a>')
    CONTACT = ('Write to <a href="mailto:frontdesk@clinic.example">us</a> or '
               '<a href="https://wa.me/911155500101">WhatsApp</a> icon@2x.png')

    def test_extract_and_links(self):
        self.assertEqual(enrich.contact_links(self.HOME, "https://clinic.example/"),
                         ["https://clinic.example/contact-us"])
        got = enrich.extract(self.CONTACT)
        self.assertEqual(got["emails"], ["frontdesk@clinic.example"])
        self.assertEqual(got["whatsapp"], "911155500101")
        self.assertEqual(enrich.extract(self.HOME)["phones"], ["+91 11 5550 0101"])

    def test_enrich_fills_only_empty_fields(self):
        pages = {"https://clinic.example": self.HOME, "https://clinic.example/contact-us": self.CONTACT}
        lead = Lead("t", "1", name="C", website="clinic.example", phone="existing")
        ok = enrich.enrich(lead, pause=0, fetcher=lambda u, **k: pages[u].encode(), allowed=lambda u: True)
        self.assertTrue(ok)
        self.assertEqual((lead.email, lead.phone, lead.whatsapp),
                         ("frontdesk@clinic.example", "existing", "911155500101"))

    def test_robots_refusal_means_no_fetch(self):
        lead = Lead("t", "1", name="C", website="https://clinic.example")
        boom = lambda u, **k: (_ for _ in ()).throw(AssertionError("must not fetch"))
        self.assertFalse(enrich.enrich(lead, fetcher=boom, allowed=lambda u: False))
        self.assertEqual(lead.email, "")


class Cli(unittest.TestCase):
    def test_city_config_is_valid(self):
        cities = load_cities()
        self.assertGreater(len(cities), 30)
        for c in cities:
            self.assertTrue(-90 <= float(c["lat"]) <= 90 and -180 <= float(c["lon"]) <= 180, c)
            self.assertEqual(len(c["cc"]), 2)
            self.assertIn(c["review_offer"], ("restricted", "allowed-with-rules", "check"))
        self.assertEqual(len({c["city"] for c in cities}), len(cities))

    def test_collect_export_end_to_end(self):
        with open(os.path.join(HERE, "fixtures", "overpass_sample.json")) as f:
            payload = json.load(f)
        orig, overpass.fetch_json = overpass.fetch_json, lambda *a, **k: payload
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, out = os.path.join(tmp, "l.sqlite"), os.path.join(tmp, "out.csv")
                roster = os.path.join(tmp, "r.csv")
                with open(roster, "w") as f:
                    f.write("doctor_name,specialty,hospital,city,source_url\n"
                            "Dr Anita Fictionrao,Dermatology,Sample General Hospital,New Delhi,https://sgh.example\n")
                main(["--db", db, "collect", "--city", "New Delhi", "--pause", "0"])
                main(["--db", db, "crossmatch", roster])
                main(["--db", db, "export", out, "--consultants"])
                with open(out) as f:
                    lines = f.read().strip().splitlines()
                self.assertEqual(len(lines), 2)
                self.assertIn("Fictionrao", lines[1])
        finally:
            overpass.fetch_json = orig


if __name__ == "__main__":
    unittest.main()
