"""The service itself, run for one clinic: messages to the clinic's own patients, from the clinic's list.

    clinics/<id>/clinic.toml    the clinic: name, doctor, address, country, mailbox, what is switched on
    clinics/<id>/patients.csv   the clinic's export: name, email, phone, consent, appointment, last_visit,
                                review_due, missed  (column names are matched loosely, see COLUMNS)
    clinics/<id>/state.sqlite   what was sent, who asked to stop, who answered (the record behind the reports)

What goes out, each once and only to patients who said yes to messages (consent column):

    reminder   the day before a booked appointment
    postvisit  the day after a visit: "how are you feeling?" (a reply reaches the clinic)
    feedback   2-7 days after a visit: a Google review request where the country allows clinics to ask
               (REVIEW_COUNTRIES), private feedback everywhere else. India: private feedback only.
    followup   the review visit the doctor advised: 2 days before it is due (or as soon as the list shows it,
               up to 10 days late), and once more at least 4 days later if the patient has still not booked
    rebook     after a missed appointment: a new time offered, once

Rules held here, whatever clinic.toml says: no message without consent; no medical detail in any message
unless the clinic switches show_reason on; every patient asked for a review the same way, nothing offered
in return (FORBIDDEN_REVIEW); "stop" is final; nothing is sent until approved = true.

A test run sends every message to one address of yours instead of to the patients:
    cg clinic run demo --to you@gmail.com
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from leadgen.util import get_tz

from .mail import build_message
from .mail.verify import EMAIL_RE
from .outreach.classify import NEGATIVE, NEGATIVE_SHORT, new_text, snippet

# Where a clinic may ask its patients for a public review (docs/STRATEGY.md). Everywhere else: private feedback.
REVIEW_COUNTRIES = {"US", "GB"}
DEFAULTS = {
    "name": "", "doctor": "", "sender_name": "", "address": "", "phone": "", "country": "IN",
    "timezone": "Asia/Kolkata", "review_link": "", "notify_email": "", "mailbox": 1, "approved": False,
    "daily_limit": 150, "window_start": 9, "window_end": 20, "show_reason": False,
    "messages": {"reminder": True, "postvisit": True, "feedback": True, "followup": True, "rebook": True},
}
COLUMNS = {"name": ("name", "patient", "patient name", "full name", "first name"),
           "email": ("email", "e-mail", "email address", "mail"),
           "phone": ("phone", "mobile", "phone number", "contact", "whatsapp"),
           "consent": ("consent", "messages", "agreed", "opt-in", "optin", "reminders"),
           "appointment": ("appointment", "next appointment", "next visit", "booked", "appointment date"),
           "last_visit": ("last_visit", "last visit", "visit", "last seen", "visited"),
           "review_due": ("review_due", "review due", "follow-up", "follow up", "followup", "come back", "recall"),
           "reason": ("reason", "review reason", "follow-up reason", "for"),
           "missed": ("missed", "missed appointment", "no-show", "no show", "dna")}
YES = {"yes", "y", "true", "1", "x", "ok", "agreed", "opted in", "opt-in"}
ORDER = ["reminder", "rebook", "followup", "postvisit", "feedback"]
LABELS = {"reminder": "Appointment reminder", "rebook": "Missed visit: new time offered",
          "followup": "Follow-up the doctor advised", "postvisit": "Post-visit check",
          "feedback": "Private feedback request", "review": "Google review request"}

TEXTS = {
    "reminder": ("Your appointment at {clinic} {when_short}",
                 "Hello {first},\n\nThis is a reminder of your appointment with {doctor} {when}.\n\n"
                 "Reply 1 to confirm, or R if you need another time and we will call you.\n\n{clinic}\n{footer}"),
    "postvisit": ("How are you feeling, {first}?",
                  "Hello {first},\n\nThank you for visiting {clinic} yesterday. How are you feeling today?\n\n"
                  "Reply 1 if all is well, or 2 if you would like the clinic to call you.\n\n{clinic}\n{footer}"),
    "feedback": ("A quick question from {clinic}",
                 "Hello {first},\n\nHow was your visit to {clinic}? A reply with a number from 1 (poor) to 5 "
                 "(excellent), and anything you would like us to know, is enough.\n\nYour answer goes only to the "
                 "clinic and is never published.\n\n{clinic}\n{footer}"),
    "review": ("Thank you for visiting {clinic}",
               "Hello {first},\n\nThank you for visiting {clinic}. If you would like to share your experience, you "
               "can leave a Google review here:\n{review_link}\n\nShort or long, your honest opinion is what "
               "counts.\n\n{clinic}\n{footer}"),
    "followup": [("{doctor} would like to see you again",
                  "Hello {first},\n\n{doctor} asked to see you again{reason} around {due}. Reply with a day and "
                  "time that suits you, and we will book it.\n\n{clinic}\n{footer}"),
                 ("Your follow-up visit at {clinic}",
                  "Hello {first},\n\nA gentle reminder that the follow-up visit {doctor} advised{reason} is now due. "
                  "Reply with a day that suits you, or call us{phone_line}.\n\n{clinic}\n{footer}")],
    "rebook": ("We missed you at {clinic}",
               "Hello {first},\n\nWe missed you at your appointment on {missed}. Would you like a new time? Reply "
               "with a day that suits you, and we will book it.\n\n{clinic}\n{footer}"),
}
# What a review request may never say (Google's review rules; the FTC rule on reviews; the CMA's guidance).
FORBIDDEN_REVIEW = re.compile(r"\b(5[\s-]?stars?|five[\s-]?stars?|discount|voucher|coupon|free\b|prize|raffle|"
                              r"in return|reward|gift|if you (were|are) happy|positive review)\b", re.I)
CONFIRM = re.compile(r"^\s*(1|yes|confirm(ed)?|ok(ay)?|coming|i will come)\b", re.I)
CHANGE = re.compile(r"^\s*(r|2|change|reschedule|another time|call me|cannot come|can't come)\b", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS sent (id INTEGER PRIMARY KEY, email TEXT NOT NULL, kind TEXT NOT NULL, step INTEGER NOT NULL,
  ref TEXT NOT NULL, at REAL NOT NULL, day TEXT NOT NULL, msgid TEXT, status TEXT NOT NULL, test_to TEXT);
CREATE INDEX IF NOT EXISTS sent_email ON sent(email);
CREATE TABLE IF NOT EXISTS stops (email TEXT PRIMARY KEY, reason TEXT, at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS replies (id INTEGER PRIMARY KEY, email TEXT, at REAL NOT NULL, kind TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


class ClinicError(ValueError):
    pass


@dataclass
class Patient:
    email: str
    name: str = ""
    phone: str = ""
    consent: bool = False
    appointment: datetime | None = None
    last_visit: date | None = None
    review_due: date | None = None
    reason: str = ""
    missed: date | None = None

    @property
    def first(self) -> str:
        first = self.name.strip().split(" ")[0].strip(",.") if self.name.strip() else ""
        return first.capitalize() if first.isalpha() and len(first) > 1 else "there"


@dataclass
class Due:
    patient: Patient
    kind: str                  # one of ORDER
    step: int = 1
    ref: str = ""              # what it is about: the appointment, the visit, the due date
    subject: str = ""
    body: str = ""
    label: str = field(default="")


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def parse_date(text: str) -> date | None:
    """A date as clinic software exports it: 2026-11-03, 03/11/2026 (day first, as in India and the UK),
    3 Nov 2026 ..."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%d/%m/%y"):
        for candidate in (text, text.split(" ")[0]):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def parse_when(text: str) -> datetime | None:
    """An appointment: a date and a time ("2026-11-14 17:20", "14/11/2026 5:20 PM"); a date alone is 09:00."""
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y %I:%M %p", "%Y-%m-%d %I:%M %p",
                "%d-%m-%Y %H:%M", "%d %b %Y %H:%M", "%d %b %Y %I:%M %p"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    d = parse_date(text)
    return datetime(d.year, d.month, d.day, 9, 0) if d else None


def nice_day(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%b')}"


def nice_time(t: datetime) -> str:
    h = t.hour % 12 or 12
    return f"{h}{'' if t.minute == 0 else f':{t.minute:02d}'} {'am' if t.hour < 12 else 'pm'}"


class Clinic:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.id = self.folder.name
        path = self.folder / "clinic.toml"
        if not path.is_file():
            raise ClinicError(f"no clinic '{self.id}': {path} does not exist (cg clinic new {self.id})")
        try:
            self.cfg = _merge(DEFAULTS, tomllib.loads(path.read_text(encoding="utf-8")))
        except tomllib.TOMLDecodeError as exc:
            raise ClinicError(f"{path} is not valid: {exc}") from exc
        self.cfg["country"] = str(self.cfg["country"] or "IN").upper()
        self.conn = sqlite3.connect(str(self.folder / "state.sqlite"), timeout=30, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ settings and the list
    @property
    def reviews_allowed(self) -> bool:
        return self.cfg["country"] in REVIEW_COUNTRIES and str(self.cfg["review_link"]).startswith("http")

    def problems(self) -> list[str]:
        c = self.cfg
        out = [f"clinic.toml: {k} is missing" for k in ("name", "doctor", "sender_name", "address")
               if not str(c.get(k) or "").strip()]
        if c["country"] in REVIEW_COUNTRIES and c["messages"]["feedback"] and not str(c["review_link"]).startswith("http"):
            out.append("clinic.toml: review_link is missing (the clinic's Google review link); until then patients "
                       "get the private feedback question")
        if c["country"] not in REVIEW_COUNTRIES and str(c["review_link"]).strip():
            out.append(f"clinic.toml: review_link is ignored - clinics in {c['country']} do not ask patients for "
                       f"public reviews here (docs/STRATEGY.md)")
        for kind in ("review", "feedback"):
            if FORBIDDEN_REVIEW.search(" ".join(self._text(kind))):
                out.append(f"the {kind} text offers something or asks for a good review: that is not allowed")
        if not (self.folder / "patients.csv").is_file():
            out.append("patients.csv is missing (the clinic's export)")
        return out

    def _text(self, kind: str, step: int = 1) -> tuple[str, str]:
        own = (self.cfg.get("texts") or {}).get(kind)
        t = own if own else TEXTS[kind]
        if isinstance(t, dict):
            return t.get("subject", ""), t.get("body", "")
        if isinstance(t, list):
            x = t[min(step - 1, len(t) - 1)]
            return (x.get("subject", ""), x.get("body", "")) if isinstance(x, dict) else x
        return t

    def patients(self) -> list[Patient]:
        path = self.folder / "patients.csv"
        if not path.is_file():
            return []
        with path.open(encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = list(csv.DictReader(fh, dialect=dialect))
        if not rows:
            return []
        head = {h.strip().lower(): h for h in rows[0] if h}
        col = {k: next((head[n] for n in names if n in head), None) for k, names in COLUMNS.items()}
        if not col["email"]:
            raise ClinicError(f"{path}: no e-mail column found (name it email)")
        out, seen = [], set()
        for r in rows:
            email = str(r.get(col["email"]) or "").strip().lower()
            if not EMAIL_RE.match(email) or email in seen:
                continue
            seen.add(email)
            g = lambda k: str(r.get(col[k]) or "").strip() if col[k] else ""  # noqa: E731
            out.append(Patient(email=email, name=g("name"), phone=g("phone"), consent=g("consent").lower() in YES,
                               appointment=parse_when(g("appointment")), last_visit=parse_date(g("last_visit")),
                               review_due=parse_date(g("review_due")), reason=g("reason"), missed=parse_date(g("missed"))))
        return out

    # ------------------------------------------------------------------ who is due
    def _done(self, email: str, kind: str, ref: str) -> list:
        return self.conn.execute("SELECT * FROM sent WHERE email=? AND kind=? AND ref=? AND status='sent' ORDER BY at",
                                 (email, kind, ref)).fetchall()

    def _now_local(self, now: float) -> datetime:
        return datetime.fromtimestamp(now, get_tz(self.cfg["timezone"])).replace(tzinfo=None)

    def due(self, now: float | None = None) -> list[Due]:
        """Today's messages, the most time-critical first, within the clinic's daily limit."""
        now = time.time() if now is None else now
        on = self.cfg["messages"]
        local = self._now_local(now)
        today = local.date()
        stops = {r["email"] for r in self.conn.execute("SELECT email FROM stops")}
        out: list[Due] = []
        for p in self.patients():
            if p.email in stops or not p.consent:
                continue
            booked_ahead = p.appointment is not None and p.appointment > local
            # the day before a booked appointment (from 24 h to 2 h before it)
            if on["reminder"] and booked_ahead and timedelta(hours=2) < p.appointment - local <= timedelta(hours=26):
                ref = p.appointment.isoformat(timespec="minutes")
                if not self._done(p.email, "reminder", ref):
                    out.append(Due(p, "reminder", 1, ref))
            # a missed appointment in the last two weeks, nothing booked since: one offer of a new time
            if on["rebook"] and p.missed and 0 <= (today - p.missed).days <= 14 and not booked_ahead:
                if not self._done(p.email, "rebook", p.missed.isoformat()):
                    out.append(Due(p, "rebook", 1, p.missed.isoformat()))
            # the review visit the doctor advised: 2 days before it is due, again 3 days after if still not booked
            if on["followup"] and p.review_due:
                ref = p.review_due.isoformat()
                booked = p.appointment is not None and p.appointment.date() >= p.review_due - timedelta(days=7)
                done = self._done(p.email, "followup", ref)
                late = (today - p.review_due).days
                if not booked:
                    if not done and -2 <= late <= 10:
                        out.append(Due(p, "followup", 1, ref))
                    elif len(done) == 1 and 3 <= late <= 21 and now - done[0]["at"] >= 4 * 86400:
                        out.append(Due(p, "followup", 2, ref))
            if p.last_visit and p.last_visit < today:
                age = (today - p.last_visit).days
                ref = p.last_visit.isoformat()
                if on["postvisit"] and age == 1 and not self._done(p.email, "postvisit", ref):
                    out.append(Due(p, "postvisit", 1, ref))
                if on["feedback"] and 2 <= age <= 7 and not self._done(p.email, "feedback", ref):
                    asked = self.conn.execute("SELECT MAX(at) FROM sent WHERE email=? AND kind='feedback' AND status='sent'",
                                              (p.email,)).fetchone()[0]
                    if not (asked and now - asked < 90 * 86400):
                        out.append(Due(p, "feedback", 1, ref))
        out.sort(key=lambda d: (ORDER.index(d.kind), -d.step))
        sent_today = self.conn.execute("SELECT COUNT(*) FROM sent WHERE day=? AND status='sent'",
                                       (today.isoformat(),)).fetchone()[0]
        out = out[:max(0, int(self.cfg["daily_limit"]) - sent_today)]
        for d in out:
            d.subject, d.body = self.compose(d, local)
            d.label = LABELS["review" if d.kind == "feedback" and self.reviews_allowed else d.kind]
        return out

    def compose(self, d: Due, local: datetime | None = None) -> tuple[str, str]:
        c = self.cfg
        kind = "review" if d.kind == "feedback" and self.reviews_allowed else d.kind
        subject, body = self._text(kind, d.step)
        p = d.patient
        when = when_short = ""
        if p.appointment:
            day = p.appointment.date()
            today = (local or datetime.now()).date()
            word = "tomorrow" if day == today + timedelta(days=1) else ("today" if day == today else f"on {nice_day(day)}")
            when = f"{word}, {nice_day(day)}, at {nice_time(p.appointment)}" if word in ("today", "tomorrow") \
                else f"{word} at {nice_time(p.appointment)}"
            when_short = f"{word} at {nice_time(p.appointment)}"
        reason = f" for your {p.reason}" if c["show_reason"] and p.reason else ""
        phone = str(c.get("phone") or "").strip()
        ctx = {"first": p.first, "clinic": c["name"], "doctor": c["doctor"] or c["name"], "when": when,
               "when_short": when_short, "due": nice_day(p.review_due) if p.review_due else "",
               "missed": nice_day(p.missed) if p.missed else "", "reason": reason, "review_link": c["review_link"],
               "phone_line": f" on {phone}" if phone else "",
               "footer": f"{c['address']}\nNo more messages from us? Reply STOP."}
        fill = lambda s: re.sub(r"\n{3,}", "\n\n", s.format_map(_Keep(ctx))).strip()  # noqa: E731
        return fill(subject), fill(body)

    # ------------------------------------------------------------------ sending and answers
    def in_hours(self, now: float) -> bool:
        h = self._now_local(now).hour
        return int(self.cfg["window_start"]) <= h < int(self.cfg["window_end"])

    def record(self, d: Due, now: float, msgid: str, status: str = "sent", test_to: str = "") -> None:
        day = self._now_local(now).date().isoformat()
        self.conn.execute("INSERT INTO sent(email, kind, step, ref, at, day, msgid, status, test_to) VALUES(?,?,?,?,?,?,?,?,?)",
                          (d.patient.email, d.kind, d.step, d.ref, now, day, msgid, status, test_to))

    def stop(self, email: str, reason: str, now: float | None = None) -> bool:
        cur = self.conn.execute("INSERT OR IGNORE INTO stops(email, reason, at) VALUES(?,?,?)",
                                (email.strip().lower(), reason, time.time() if now is None else now))
        return cur.rowcount > 0

    def run(self, mailbox, *, live: bool, test_to: str = "", max_messages: int | None = None, now_fn=time.time,
            sleep_fn=time.sleep, gap: float = 30.0) -> dict:
        """Read the answers, then send what is due. With test_to every message goes to that address instead
        (marked TEST), and is recorded as a test, so the real patients still get theirs later."""
        now = now_fn()
        stats = {"due": 0, "sent": 0, "failed": 0, "replies": 0, "stops": 0, "note": ""}
        if live and not test_to:
            stats.update(self.read_answers(mailbox, now))
        due = self.due(now)
        if test_to:
            due = [d for d in due if not self.conn.execute(
                "SELECT 1 FROM sent WHERE email=? AND kind=? AND ref=? AND step=? AND test_to=?",
                (d.patient.email, d.kind, d.ref, d.step, test_to)).fetchone()]
        if max_messages is not None:
            due = due[:max_messages]
        stats["due"] = len(due)
        if not live:
            return stats
        if not test_to and not self.cfg["approved"]:
            stats["note"] = "not approved yet: set approved = true in clinic.toml once the clinic has read the texts"
            return stats
        if not test_to and not self.in_hours(now):
            stats["note"] = "outside the clinic's sending hours"
            return stats
        notify = str(self.cfg.get("notify_email") or "").strip()
        for i, d in enumerate(due):
            if i:
                sleep_fn(gap)
            to = test_to or d.patient.email
            subject = f"[TEST for {d.patient.name or d.patient.email}] {d.subject}" if test_to else d.subject
            msg = build_message(sender_name=self.cfg["sender_name"], sender_addr=mailbox.address, to=to,
                                subject=subject, body=d.body, unsubscribe=not test_to)
            if notify and not test_to:
                msg["Reply-To"] = f"{notify}, {mailbox.address}"
            res = mailbox.send(msg)
            if res.ok:
                self.record(d, now_fn(), res.msgid or msg["Message-ID"], "test" if test_to else "sent", test_to)
                stats["sent"] += 1
            elif res.status == "invalid" and not test_to:
                self.record(d, now_fn(), "", "bounced")
                self.stop(d.patient.email, "address rejected by the mail server", now_fn())
                stats["failed"] += 1
            else:
                stats["failed"] += 1
                stats["note"] = f"sending stopped: {res.status} {res.detail[:120]}"
                break
        mailbox.close()
        return stats

    def read_answers(self, mailbox, now: float) -> dict:
        """Patients' answers: "stop" is final, "1"/"yes" confirms, "R"/"2" asks for a call; all kept for the clinic."""
        known = {r["email"] for r in self.conn.execute("SELECT DISTINCT email FROM sent WHERE status='sent'")}
        if not known:
            return {"replies": 0, "stops": 0}
        cursor = self.conn.execute("SELECT value FROM meta WHERE key='cursor'").fetchone()
        try:
            events, new_cursor = mailbox.scan(known_emails=known, known_msgids={},
                                              cursor=json.loads(cursor[0]) if cursor else {})
        except Exception:  # noqa: BLE001 - the inbox not answering must not stop today's reminders
            return {"replies": 0, "stops": 0}
        replies = stops = 0
        for ev in events:
            if ev.kind == "bounce":
                stops += self.stop(ev.email, "bounced", now)
                continue
            if ev.reply_kind == "auto":
                continue
            text = new_text(ev.text)
            first = text.split("\n")[0] if text else ""
            if re.match(r"^\s*stop\b", first, re.I) or ev.reply_kind == "negative" or NEGATIVE_SHORT.match(first) \
                    or NEGATIVE.search(text):
                kind = "stop"
                stops += self.stop(ev.email, "asked to stop", now)
            elif CONFIRM.match(first):
                kind = "confirmed"
            elif CHANGE.match(first):
                kind = "call back"
            else:
                kind = "message"
            self.conn.execute("INSERT INTO replies(email, at, kind, text) VALUES(?,?,?,?)",
                              (ev.email, now, kind, snippet(text, 1000)))
            replies += 1
        self.conn.execute("INSERT INTO meta(key, value) VALUES('cursor', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (json.dumps(new_cursor),))
        return {"replies": replies, "stops": stops}

    # ------------------------------------------------------------------ the doctor's morning sheet
    def sheet(self, now: float | None = None) -> dict:
        """What the doctor reads every morning: today's list, follow-ups due and overdue, missed visits, answers."""
        now = time.time() if now is None else now
        local = self._now_local(now)
        today = local.date()
        patients = self.patients()
        by_email = {p.email: p for p in patients}
        appts = sorted((p for p in patients if p.appointment and p.appointment.date() == today), key=lambda p: p.appointment)
        tomorrow = [p for p in patients if p.appointment and p.appointment.date() == today + timedelta(days=1)]
        confirmed = {r["email"] for r in self.conn.execute("SELECT email FROM replies WHERE kind='confirmed'")}
        due_week, overdue = [], []
        for p in patients:
            if not p.review_due:
                continue
            booked = p.appointment is not None and p.appointment.date() >= p.review_due - timedelta(days=7)
            if booked:
                continue
            if p.review_due < today - timedelta(days=3):
                overdue.append(p)
            elif p.review_due <= today + timedelta(days=7):
                due_week.append(p)
        missed = [p for p in patients if p.missed and 0 <= (today - p.missed).days <= 14
                  and not (p.appointment and p.appointment > local)]
        since = now - 86400
        sent = {r["kind"]: r["n"] for r in self.conn.execute(
            "SELECT kind, COUNT(*) AS n FROM sent WHERE status='sent' AND at>=? GROUP BY kind", (since,))}
        answers = [dict(r) for r in self.conn.execute(
            "SELECT email, kind, text FROM replies WHERE at>=? ORDER BY at", (now - 2 * 86400,))]
        for a in answers:
            a["name"] = by_email.get(a["email"]).name if a["email"] in by_email else a["email"]
        return {"clinic": self.cfg["name"], "date": today.isoformat(),
                "today": [(nice_time(p.appointment), p.name, "confirmed" if p.email in confirmed else "") for p in appts],
                "tomorrow": len(tomorrow), "followups_due": [(p.name, nice_day(p.review_due)) for p in due_week],
                "followups_overdue": [(p.name, nice_day(p.review_due)) for p in overdue],
                "missed": [(p.name, nice_day(p.missed)) for p in missed], "sent_last_24h": sent,
                "answers": answers, "stopped": self.conn.execute("SELECT COUNT(*) FROM stops").fetchone()[0],
                "no_consent": sum(1 for p in patients if not p.consent)}

    def report(self, days: int = 30, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        since = now - days * 86400
        per = {r["kind"]: r["n"] for r in self.conn.execute(
            "SELECT kind, COUNT(*) AS n FROM sent WHERE status='sent' AND at>=? GROUP BY kind", (since,))}
        answers = {r["kind"]: r["n"] for r in self.conn.execute(
            "SELECT kind, COUNT(*) AS n FROM replies WHERE at>=? GROUP BY kind", (since,))}
        tests = self.conn.execute("SELECT COUNT(*) FROM sent WHERE status='test' AND at>=?", (since,)).fetchone()[0]
        return {"clinic": self.cfg["name"], "days": days, "messages": per, "answers": answers, "tests": tests,
                "stops": self.conn.execute("SELECT COUNT(*) FROM stops WHERE at>=?", (since,)).fetchone()[0]}


class _Keep(dict):
    def __missing__(self, key):
        return "{" + key + "}"


CLINIC_TOML = '''# One clinic. Fill it in, put the clinic's export next to it as patients.csv, then:  cg clinic preview {id}
name = ""                     # the clinic, as its patients know it: "Dr. Sen's Dental Clinic"
doctor = ""                   # who the patients see: "Dr. A. Sen"
sender_name = ""              # who the messages come from: "Dr. Sen's Dental Clinic"
address = ""                  # the clinic's address, at the end of every message
phone = ""                    # the clinic's phone, offered in the second follow-up reminder
country = "IN"                # IN, US, GB ... : decides whether patients may be asked for Google reviews
timezone = "Asia/Kolkata"
review_link = ""              # US and UK only: the clinic's Google review link. Ignored in India.
notify_email = ""             # the clinic's own e-mail: patients' replies also go there
mailbox = 1                   # which of your mailboxes (settings.txt MAILBOX_n) sends for this clinic
daily_limit = 150
show_reason = false           # true: follow-up reminders name the reason ("for your filling check")
approved = false              # true only after the clinic has signed and read the texts ( cg clinic preview )

[messages]
reminder = true               # the day before a booked appointment
postvisit = true              # the day after a visit
feedback = true               # 2-7 days after a visit: Google review (US/UK, with review_link) or private feedback
followup = true               # the review visit the doctor advised
rebook = true                 # a new time after a missed appointment
'''

DEMO_PEOPLE = [
    # name, appointment (days, "HH:MM") | None, last visit (days ago) | None, review due (days) | None, missed (days ago) | None, consent
    ("Ananya Bose", None, 9, 2, None, True),
    ("Rahul Mehra", None, 1, 13, None, True),
    ("Priya Sharma", (1, "10:00"), 30, None, None, True),
    ("Arjun Nair", (1, "17:20"), None, None, None, True),
    ("Farida Khan", None, 180, -4, None, True),
    ("Joseph D'Souza", None, 45, None, 2, True),
    ("Meera Iyer", None, 3, None, None, True),
    ("Kabir Malhotra", (0, "18:00"), 60, None, None, True),
    ("Sana Ali", None, 4, None, None, False),
    ("Vikram Rao", (6, "11:00"), 40, 5, None, True),
]


DEMO_TZ = {"IN": "Asia/Kolkata", "US": "America/New_York", "GB": "Europe/London"}


def make_demo(folder: Path, today: date | None = None, country: str = "IN") -> Path:
    """A demo clinic with invented patients, dated around today, at reserved example.com addresses (they can
    never receive anything): see every kind of message with  cg clinic preview demo , or have them all sent to
    yourself with  cg clinic run demo --to you@gmail.com ."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tz = DEMO_TZ.get(country, "Asia/Kolkata")
    today = today or datetime.now(get_tz(tz)).date()        # the clinic's own date, not the device's
    for stale in ("state.sqlite", "state.sqlite-journal"):
        (folder / stale).unlink(missing_ok=True)              # a fresh demo starts with nothing sent
    toml = (CLINIC_TOML.replace("{id}", folder.name)
            .replace('name = ""', 'name = "Dr. Sen\'s Dental Clinic (demo)"', 1)
            .replace('doctor = ""', 'doctor = "Dr. A. Sen"', 1)
            .replace('sender_name = ""', 'sender_name = "Dr. Sen\'s Dental Clinic"', 1)
            .replace('address = ""', 'address = "14 Example Road, Salt Lake, Kolkata"', 1)
            .replace('country = "IN"', f'country = "{country}"', 1)
            .replace('timezone = "Asia/Kolkata"', f'timezone = "{tz}"', 1))
    if country in REVIEW_COUNTRIES:
        toml = toml.replace('review_link = ""', 'review_link = "https://g.page/r/your-clinic-link/review"', 1)
    (folder / "clinic.toml").write_text(toml, encoding="utf-8")
    rows = []
    for i, (name, appt, last, due, missed, consent) in enumerate(DEMO_PEOPLE, start=1):
        slug = re.sub(r"[^a-z]", "", name.lower().split(" ")[0])
        rows.append({
            "name": name, "email": f"{slug}.demo{i}@example.com", "phone": f"+91 98300 00{i:03d}",
            "consent": "yes" if consent else "no",
            "appointment": f"{(today + timedelta(days=appt[0])).isoformat()} {appt[1]}" if appt else "",
            "last_visit": (today - timedelta(days=last)).isoformat() if last is not None else "",
            "review_due": (today + timedelta(days=due)).isoformat() if due is not None else "",
            "reason": "filling check" if due is not None else "",
            "missed": (today - timedelta(days=missed)).isoformat() if missed is not None else ""})
    with (folder / "patients.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return folder
