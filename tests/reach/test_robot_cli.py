"""The robot's timetable, the commands' helpers, and the files a fresh tablet starts from."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from outreach_helpers import Clock, FakeMailbox, box, engine, make_leads

from clinicreach import cli, robot
from clinicreach import settings as S
from clinicreach.outreach import config as C
from clinicreach.outreach.store import Store

ROOT = Path(__file__).resolve().parent.parent.parent
IST = ZoneInfo("Asia/Kolkata")


def ts(text: str) -> float:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=IST).timestamp()


def test_jobs_come_due_once_and_a_missed_one_is_caught_up_within_its_time():
    leads, emails = robot.JOBS["leads"], robot.JOBS["emails"]
    assert robot.due_slot(leads, {}, ts("2026-11-11 18:29"), None) is None            # evening: after clinic hours
    slot = robot.due_slot(leads, {}, ts("2026-11-11 18:31"), None)
    assert slot == ts("2026-11-11 18:30")
    assert robot.due_slot(leads, {}, ts("2026-11-11 19:30"), slot) is None           # done for today
    assert robot.due_slot(leads, {}, ts("2026-11-12 00:00"), None) == slot            # tablet was off: still that day's
    assert robot.due_slot(leads, {}, ts("2026-11-12 01:30"), None) is None            # too late: tomorrow evening
    assert robot.due_slot(emails, {}, ts("2026-11-11 10:40"), ts("2026-11-11 09:35")) == ts("2026-11-11 10:35")
    assert robot.due_slot(emails, {}, ts("2026-11-11 10:25"), ts("2026-11-11 09:35")) is None
    assert robot.next_slot(emails, {}, ts("2026-11-11 23:50")) == ts("2026-11-12 00:35")
    assert robot.due_slot(leads, {"ROBOT_LEADS_TIME": "21:15"}, ts("2026-11-11 21:16"), None) == ts("2026-11-11 21:15")


def test_emails_come_before_the_other_jobs_and_a_switched_off_job_never_runs():
    now = ts("2026-11-11 08:36")
    assert robot.pick_due(now, {}, {})[0].name == "emails"
    done = {"jobs": {"emails": {"slot": ts("2026-11-11 08:35")}}}
    assert robot.pick_due(now, done, {})[0].name == "update"
    assert robot.pick_due(now, done, {"ROBOT_AUTO_UPDATE": "no", "ROBOT_BACKUP": "no", "ROBOT_LEADS": "no"}) is None


def test_no_email_run_is_started_while_every_market_sleeps(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "load", lambda *a, **k: {"MARKETS": "us,gb"})
    assert robot.office_hours_somewhere(ts("2026-11-11 21:00"))          # 15:30 in London, 10:30 in New York
    assert not robot.office_hours_somewhere(ts("2026-11-11 09:00"))      # night in the US, 3:30 in London
    assert not robot.office_hours_somewhere(ts("2026-11-14 21:00"))      # a Saturday


def test_cities_are_searched_market_by_market_and_one_under_way_is_finished_first(tmp_path, monkeypatch):
    monkeypatch.setenv("WR_DATA_DIR", str(tmp_path))
    order = cli.city_order(["in", "gb", "us"])
    assert order[:4] == [("in", "kolkata"), ("gb", "london"), ("us", "washington-dc"), ("in", "new-delhi")]
    assert len(order) == 19 + 1 + 1
    assert cli.next_cities(["in", "gb"], 2) == [("in", "kolkata"), ("gb", "london")]
    (tmp_path / "in-kolkata.sqlite").write_bytes(b"")                  # searched before (and nothing open)
    assert cli.next_cities(["in", "gb"], 1) == [("gb", "london")]


def test_status_and_report_read_the_memory(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WR_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(S, "load", lambda *a, **k: {"MAILBOX_1": "gmail", "MAILBOX_1_ADDRESS": "sender1@gmail.com",
                                                    "MAILBOX_1_PASSWORD": "x", "MARKETS": "us", "LIVE": "yes"})
    clock = Clock()
    mb = FakeMailbox("sender1@gmail.com", clock=clock)
    store = Store(str(tmp_path / "outreach.sqlite"))
    engine(store, clock, [box(1)], {mb.address: mb}, leads=make_leads(30), max_emails=5).run()
    from clinicreach.mail.base import InboxEvent

    mb.inbox.append(InboxEvent("reply", mb.to()[0], "positive", "Yes, send it"))
    clock.sleep(600)
    engine(store, clock, [box(1)], {mb.address: mb}, leads=make_leads(30), max_emails=0).run()
    store.close()
    text = cli.status_text(clock.now())
    assert "LIVE" in text and "sender1@gmail.com (gmail): warm-up day-step 1 of 9, today 6 of 50" in text      # 5 first e-mails + the overview that went back
    assert "5 businesses written to" in text and "interested 1" in text
    data = cli.report_data(Store(str(tmp_path / "outreach.sqlite")), 14, "America/New_York", clock.now())
    assert data["total"]["first"] == 5 and data["total"]["positive"] == 1 and len(data["replies"]) == 1
    assert cli.cmd_report(cli.build_parser().parse_args(["report"])) == 0
    out = capsys.readouterr().out
    assert "Interested - answer these first (1)" in out and "20.0% interested" in out


def test_the_shipped_files_are_consistent():
    for sh in sorted((ROOT / "android").glob("*.sh")) + sorted((ROOT / "server").glob("*.sh")) + [ROOT / "scripts" / "run.sh"]:
        assert subprocess.run(["bash", "-n", str(sh)]).returncode == 0, sh
    o = C.load(ROOT / "config" / "outreach.toml")
    assert o["ramp"]["gmail"][:3] == [50, 100, 200] and o["ramp"]["gmail"][-1] == 500 and o["mode"] == "dry-run"
    example = S.read_file(ROOT / "settings-example.txt")
    assert example["LIVE"] == "no" and example["MARKETS"] == "in" and "MAILBOX_1_PASSWORD" not in example
    assert "SENDER_BUSINESS" not in example           # the owner types their own business name
    assert o["email"]["exclude_categories"] == ["hospital"] and o["email"]["day_tz"] == "Asia/Kolkata"
    assert S.mailboxes(example) == []                 # slots left empty are simply not there
    filled = {**example, **{f"MAILBOX_{i}_ADDRESS": f"m{i}@x.com" for i in (1, 2, 4, 5)}}
    boxes = S.mailboxes(filled)                       # 3 Gmail + 2 Outlook slots; number 3 left empty
    assert [(b.index, b.kind) for b in boxes] == [(1, "gmail"), (2, "gmail"), (4, "outlook"), (5, "outlook")]
    assert all(b.problem() for b in boxes)            # ... and each still needs its password / sign-in
    codes = ("in", "us", "gb", "ca", "au", "nz", "ie", "ae", "sg")
    for code in codes:
        m = C.load_market(code)
        assert len(m.cities) == len(C.fleet(code)) and len({p for p in m.cities}) == len(m.cities)   # prefixes unique
    prefixes = [p for code in codes for p in C.load_market(code).cities]
    assert len(prefixes) == len(set(prefixes))
    # nothing personal in the repository: no phone number, no address, no password
    text = (ROOT / "settings-example.txt").read_text() + (ROOT / "marketing" / "brochure.json").read_text()
    assert not re.search(r"\+91[\s\d]{8,}|@gmail\.com", text)
    assert (ROOT / "marketing" / "brochure.pdf").read_bytes().startswith(b"%PDF")
    assert b"edition CG-" in (ROOT / "marketing" / "brochure.pdf").read_bytes()
    brochure = (ROOT / "marketing" / "build_brochure.py").read_text().lower() + (ROOT / "marketing" / "brochure.json").read_text().lower()
    assert "google review" not in brochure and "no medical advice" in brochure
