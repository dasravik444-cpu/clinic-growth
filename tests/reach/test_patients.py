"""The service for a clinic: messages to its own patients (clinicreach/patients.py). Every patient is invented."""
from __future__ import annotations

import csv
from datetime import date, datetime
from zoneinfo import ZoneInfo

from outreach_helpers import FakeMailbox

from clinicreach import cli
from clinicreach.mail.base import InboxEvent
from clinicreach.patients import FORBIDDEN_REVIEW, TEXTS, Clinic, make_demo

IST = ZoneInfo("Asia/Kolkata")


def at(text: str, tz=IST) -> float:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=tz).timestamp()


def demo(tmp_path, country="IN", today=date(2026, 11, 16)):
    folder = make_demo(tmp_path / f"demo-{country.lower()}", today, country)
    return Clinic(folder)


def kinds(clinic, now):
    return {(d.kind, d.patient.name, d.step) for d in clinic.due(now)}


def test_the_demo_clinic_has_one_of_every_message_and_never_writes_without_consent(tmp_path):
    c = demo(tmp_path)
    due = kinds(c, at("2026-11-16 09:30"))
    assert due == {("reminder", "Priya Sharma", 1), ("reminder", "Kabir Malhotra", 1),
                   ("rebook", "Joseph D'Souza", 1), ("followup", "Ananya Bose", 1), ("followup", "Farida Khan", 1),
                   ("postvisit", "Rahul Mehra", 1), ("feedback", "Meera Iyer", 1)}
    assert "Sana Ali" not in {n for _, n, _ in due}                 # no consent: never written to
    assert "Vikram Rao" not in {n for _, n, _ in due}               # follow-up already booked
    # Arjun is booked tomorrow at 17:20: his reminder comes within 26 hours of it, not yet
    assert ("reminder", "Arjun Nair", 1) in kinds(c, at("2026-11-16 16:00"))
    for p in c.patients():
        assert p.email.endswith("@example.com")                       # invented, undeliverable addresses
    assert all("@" in p.email for p in c.patients())


def test_messages_carry_no_medical_detail_and_say_how_to_stop(tmp_path):
    c = demo(tmp_path)
    for d in c.due(at("2026-11-16 09:30")):
        assert "Reply STOP" in d.body and "14 Example Road" in d.body
        assert "filling" not in d.body.lower()                        # the reason stays out unless switched on
    reminder = next(d for d in c.due(at("2026-11-16 09:30")) if d.patient.name == "Priya Sharma")
    assert reminder.subject.endswith("tomorrow at 10 am")
    assert "Dr. A. Sen tomorrow, Tuesday 17 Nov, at 10 am" in reminder.body and "Reply 1 to confirm" in reminder.body


def test_reviews_only_where_clinics_may_ask_and_the_same_for_everyone(tmp_path):
    india = demo(tmp_path, "IN")
    meera = next(d for d in india.due(at("2026-11-16 09:30")) if d.kind == "feedback")
    assert meera.label == "Private feedback request" and "never published" in meera.body and "google" not in meera.body.lower()
    india.cfg["review_link"] = "https://g.page/r/x/review"            # even a link set by mistake changes nothing
    assert not india.reviews_allowed
    assert any("ignored" in p for p in india.problems())
    us = demo(tmp_path, "US", date(2026, 11, 16))
    meera = next(d for d in us.due(at("2026-11-16 09:30", ZoneInfo("America/New_York"))) if d.kind == "feedback")
    assert meera.label == "Google review request" and "https://g.page/r/your-clinic-link/review" in meera.body
    for text in (TEXTS["review"][1], TEXTS["feedback"][1]):
        assert not FORBIDDEN_REVIEW.search(text)
    us.cfg["texts"] = {"review": {"subject": "Thanks", "body": "Leave us 5 stars and get a discount"}}
    assert any("not allowed" in p for p in us.problems())


def test_a_test_run_sends_everything_to_the_owner_only_and_patients_still_get_theirs(tmp_path):
    c = demo(tmp_path)
    c.cfg.update(approved=False)
    mb = FakeMailbox("clinic@gmail.com")
    stats = c.run(mb, live=True, test_to="me@gmail.com", now_fn=lambda: at("2026-11-16 09:30"), sleep_fn=lambda s: None)
    assert stats["sent"] == 7 and set(mb.to()) == {"me@gmail.com"}
    subjects = [str(m["Subject"]) for _, m in mb.sent]
    assert any(s.startswith("[TEST for Priya Sharma] ") for s in subjects)
    again = c.run(FakeMailbox("clinic@gmail.com"), live=True, test_to="me@gmail.com", now_fn=lambda: at("2026-11-16 10:30"),
                  sleep_fn=lambda s: None)
    assert again["sent"] == 0                                           # a test is not sent twice
    assert len(c.due(at("2026-11-16 10:30"))) == 7                     # ... and the patients still get theirs


def test_a_real_run_needs_approval_and_clinic_hours_then_each_message_goes_once(tmp_path):
    c = demo(tmp_path)
    mb = FakeMailbox("clinic@gmail.com")
    assert c.run(mb, live=True, now_fn=lambda: at("2026-11-16 09:30"))["note"].startswith("not approved")
    c.cfg["approved"] = True
    assert c.run(mb, live=True, now_fn=lambda: at("2026-11-16 07:00"))["note"] == "outside the clinic's sending hours"
    stats = c.run(mb, live=True, now_fn=lambda: at("2026-11-16 09:30"), sleep_fn=lambda s: None)
    assert stats["sent"] == 7 and "sana.demo9@example.com" not in mb.to()
    assert c.run(FakeMailbox("clinic@gmail.com"), live=True, now_fn=lambda: at("2026-11-16 11:30"),
                 sleep_fn=lambda s: None)["sent"] == 0


def test_answers_are_marked_and_stop_is_final(tmp_path):
    c = demo(tmp_path)
    c.cfg["approved"] = True
    mb = FakeMailbox("clinic@gmail.com")
    c.run(mb, live=True, now_fn=lambda: at("2026-11-16 09:30"), sleep_fn=lambda s: None)
    mb.inbox += [InboxEvent("reply", "priya.demo3@example.com", "", "1"),
                 InboxEvent("reply", "kabir.demo8@example.com", "", "R, I cannot come today"),
                 InboxEvent("reply", "arjun.demo4@example.com", "", "who is this?"),     # never written to: ignored
                 InboxEvent("reply", "ananya.demo1@example.com", "", "STOP"),
                 InboxEvent("reply", "meera.demo7@example.com", "", "5 - very gentle, thank you")]
    stats = c.run(mb, live=True, now_fn=lambda: at("2026-11-16 12:30"), sleep_fn=lambda s: None)
    assert stats["replies"] == 4 and stats["stops"] == 1
    sheet = c.sheet(at("2026-11-16 12:40"))
    marks = {x["name"]: x["kind"] for x in sheet["answers"]}
    assert marks == {"Priya Sharma": "confirmed", "Kabir Malhotra": "call back", "Ananya Bose": "stop", "Meera Iyer": "message"}
    assert sheet["stopped"] == 1 and sheet["no_consent"] == 1
    # Ananya asked to stop: her second follow-up reminder never goes, whatever the list says
    assert not [d for d in c.due(at("2026-11-21 09:30")) if d.patient.name == "Ananya Bose"]


def test_the_second_follow_up_waits_and_stops_once_the_patient_books(tmp_path):
    c = demo(tmp_path)
    c.cfg["approved"] = True
    c.run(FakeMailbox("c@gmail.com"), live=True, now_fn=lambda: at("2026-11-16 09:30"), sleep_fn=lambda s: None)
    farida = lambda now: [d.step for d in c.due(now) if d.patient.name == "Farida Khan"]   # noqa: E731
    assert farida(at("2026-11-18 09:30")) == []                       # too soon after the first
    assert farida(at("2026-11-20 09:30")) == [2]
    path = c.folder / "patients.csv"
    rows = list(csv.DictReader(path.open()))
    for r in rows:
        if r["name"] == "Farida Khan":
            r["appointment"] = "2026-11-24 11:00"                    # she booked
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert farida(at("2026-11-20 09:30")) == []


def test_the_morning_sheet(tmp_path):
    s = demo(tmp_path).sheet(at("2026-11-16 08:00"))
    assert s["today"] == [("6 pm", "Kabir Malhotra", "")]
    assert s["tomorrow"] == 2
    assert s["followups_due"] == [("Ananya Bose", "Wednesday 18 Nov")]
    assert s["followups_overdue"] == [("Farida Khan", "Thursday 12 Nov")]
    assert s["missed"] == [("Joseph D'Souza", "Saturday 14 Nov")]


def test_the_clinic_commands(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CG_CLINICS_DIR", str(tmp_path))
    monkeypatch.setattr(cli.S, "load", lambda *a, **k: {})
    assert cli.main(["clinic", "demo"]) == 0
    assert cli.main(["clinic", "list"]) == 0 and "demo" in capsys.readouterr().out
    assert cli.main(["clinic", "preview", "demo"]) == 0
    out = capsys.readouterr().out
    assert "10 patients in the list (9 agreed to messages)" in out and "Nothing goes to patients until" in out
    assert cli.main(["clinic", "sheet", "demo"]) == 0 and "Follow-ups overdue" in capsys.readouterr().out
    assert cli.main(["clinic", "run", "demo"]) == 1                     # no mailbox set up
    assert cli.main(["clinic", "new", "sen-dental"]) == 0
    assert (tmp_path / "sen-dental" / "clinic.toml").read_text().count("approved = false") == 1
