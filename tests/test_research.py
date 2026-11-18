"""Doctor research from their own websites: only what the page says next to the doctor's name, never overwriting.
All names, sites and numbers here are invented."""
from leadgen.net import Response

from clinicleads import profile as P
from clinicleads import research as R

HOME = """<html><head><title>Dr. Anita Fictionaya | Eye Surgeon</title></head><body>
<a href="/about-doctor">About the doctor</a> <a href="/contact">Contact</a> <a href="/gallery.jpg">Photos</a>
<a href="https://elsewhere.example/about">Partner</a><p>Welcome to our eye clinic.</p></body></html>"""
ABOUT = """<html><head><title>About</title></head><body>
<h2>Dr. Anita Fictionaya</h2>
<p>MBBS, MS (Ophthalmology), FRCS</p>
<p>She completed her MBBS from Fictional Medical College in 2004.</p>
<p>Over 15 years of experience in cataract surgery.</p>
<p>Consultant at Fictional City Hospital and Best Hospital.</p>
<p>Reg. No. WBMC 45678 (West Bengal Medical Council)</p>
<p>She also treats patients above age 60.</p>
<h2>Dr. Other Person</h2><p>MBBS, MD (Medicine)</p><p>Age: 52</p><p>Visiting at Second Fictional Hospital.</p>
<a href="https://wa.me/919830012345">WhatsApp us</a>
<a href="mailto:hello@drfiction.example">Write to us</a> <a href="mailto:dev@webagency.example">Site by</a>
</body></html>"""
CONTACT = "<html><head><title>Contact</title></head><body><p>Call us.</p></body></html>"


class FakeHttp:
    def __init__(self, pages, robots_ok=True):
        self.pages, self.robots_ok, self.got = pages, robots_ok, []

    def robots_allowed(self, url, user_agent=None):
        return self.robots_ok, 0.0

    def robots_reason(self, url):
        return "ok" if self.robots_ok else "disallowed"

    def get(self, url, **kw):
        self.got.append(url)
        body = self.pages.get(url)
        return Response(url=url, status=200 if body else 404, headers={"content-type": "text/html"},
                        content=(body or "").encode(), elapsed=0.0)


SITE = {"http://drfiction.example/": HOME, "http://drfiction.example/about-doctor": ABOUT,
        "http://drfiction.example/contact": CONTACT}


def test_reads_only_what_stands_next_to_the_doctor():
    http = FakeHttp(SITE)
    found = R.research(http, "drfiction.example/", "Dr. Anita Fictionaya")
    assert found["Degrees (researched)"] == "MBBS, MS (Ophthalmology), FRCS"     # not the other doctor's MD
    assert found["Qualified (year, as published)"] == "MBBS 2004"
    assert found["Experience (as published)"] == "Over 15 years of experience"
    assert found["Hospitals (researched)"] == "Fictional City Hospital"          # not "Best Hospital", not her college
    assert found["Registration no. (as published)"] == "Reg. No. WBMC 45678"
    assert "Approx. age" not in found                                            # "above age 60" is not her age
    assert found["_sources"]["Degrees (researched)"] == "http://drfiction.example/about-doctor"
    assert "98300 12345".replace(" ", "") in found["_contacts"]["WhatsApp"][0].replace(" ", "")
    assert found["_contacts"]["E-mail"][0] == "hello@drfiction.example"          # not the web designer's
    assert "http://drfiction.example/gallery.jpg" not in http.got and not any("elsewhere" in u for u in http.got)
    assert found["_note"].startswith(R.DONE_MARK)


def test_a_site_that_does_not_name_the_doctor_gives_nothing_about_them():
    found = R.research(FakeHttp(SITE), "drfiction.example/", "Dr. Ravi Notonsite")
    assert not any(found.get(c) for c in R.FACTS)
    assert "does not name" in found["_note"]


def test_robots_refusal_is_respected_and_final():
    http = FakeHttp(SITE, robots_ok=False)
    found = R.research(http, "drfiction.example/", "Dr. Anita Fictionaya")
    assert http.got == [] and "asks robots not to read it" in found["_note"] and not found["_retry"]
    row = {"Doctor": "Dr. Anita Fictionaya", "Website": "drfiction.example/"}
    R.merge(row, found, "2026-11-18")
    assert R.todo([row]) == []


def test_a_site_that_did_not_answer_is_tried_once_more(tmp_path):
    class Down(FakeHttp):
        def robots_allowed(self, url, user_agent=None):
            return False, 0.0

        def robots_reason(self, url):
            return "robots.txt unreachable (ConnectionError: refused)"

    found = R.research(Down({}), "dead.example/", "Dr. Anita Fictionaya")
    assert found["_note"] == "Website not read: the website did not answer." and found["_retry"]
    src = tmp_path / "doctors-9-test.xlsx"
    P.write_xlsx([{"Lead ID": "T-2", "Doctor": "Dr. Anita Fictionaya", "Website": "dead.example/"}], str(src), "T")
    cache = tmp_path / "c.json"
    for day, reads in (("2026-11-18", 1), ("2026-11-19", 1), ("2026-11-20", 0)):
        stats = R.run_files([src], Down({}), cache_path=cache, today=day, say=lambda *_: None)
        assert stats["sites read"] == reads
    _, (row,) = R.read_table(tmp_path / "doctors-9-test-researched.xlsx")
    assert row["Research notes"] == "Website not read: the website did not answer."
    assert row["Researched on"] == "2026-11-19 website"          # given up after the second try, not before


def test_age_only_from_a_labelled_field():
    assert R.age_in(["Dr. Anita Fictionaya\nAge: 47\nMBBS"]) == "47 (as published)"
    assert R.age_in(["Dr. Anita Fictionaya, born in 1979 in Kolkata"]) == "born 1979 (as published)"
    assert R.age_in(["Dr. Anita Fictionaya sees children aged 5 and adults above age 60"]) == ""


def test_degree_letters_alone_are_not_degrees():
    assert R.degrees_in(["Dr. Anita Fictionaya uses MS Office and DO NOT call after 9"]) == ("", "")


def test_merge_never_overwrites_and_keeps_every_source():
    row = {"Degrees (researched)": "BDS (from a web search)", "Research sources": "https://listing.example/x"}
    found = {"Degrees (researched)": "BDS, MDS", "Experience (as published)": "12 years of experience",
             "_sources": {"Degrees (researched)": "http://a.example/", "Experience (as published)": "http://a.example/b"},
             "_contacts": {}, "_note": f"{R.DONE_MARK} (2 pages)."}
    assert R.merge(row, found, "2026-11-18")
    assert row["Degrees (researched)"] == "BDS (from a web search)"
    assert row["Experience (as published)"] == "12 years of experience"
    assert row["Research sources"] == "https://listing.example/x http://a.example/b"
    assert row["Researched on"] == "2026-11-18 website"


def test_run_files_writes_a_researched_copy_and_does_not_read_a_site_twice(tmp_path):
    rows = [{"Priority": "High", "Lead ID": "CCU-1", "Doctor": "Dr. Anita Fictionaya", "Website": "drfiction.example/",
             "Key": "k1"},
            {"Priority": "High", "Lead ID": "CCU-2", "Doctor": "Dr. Web Searched", "Website": "",
             "Key": "k2"}]
    src = tmp_path / "doctors-2-kolkata.xlsx"
    R.apply_known(rows, {"CCU-2": {"Degrees (researched)": "BDS", "Research sources": "https://listing.example/2",
                                   "Research: same doctor?": "Likely: same name and field"}}, "2026-11-18")
    P.write_xlsx(rows, str(src), "All clinics, Kolkata")
    http = FakeHttp(SITE)
    cache = tmp_path / "cache.json"
    stats = R.run_files([src], http, cache_path=cache, today="2026-11-19", say=lambda *_: None)
    out = tmp_path / "doctors-2-kolkata-researched.xlsx"
    assert stats["files"] == [str(out)] and stats["sites read"] == 1
    title, got = R.read_table(out)
    assert title == "All clinics, Kolkata"
    one, two = got
    assert one["Degrees (researched)"] == "MBBS, MS (Ophthalmology), FRCS" and one["Approx. age"] == ""
    assert one["Research: same doctor?"].startswith("Sure")
    assert two["Degrees (researched)"] == "BDS" and two["Researched on"] == "2026-11-18 web search"
    n = len(http.got)
    R.run_files([src], http, cache_path=cache, today="2026-11-20", say=lambda *_: None)
    assert len(http.got) == n                       # read once, kept
