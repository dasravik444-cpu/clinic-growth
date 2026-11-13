"""The words we send. Plain text, short, no links, no images, no prices, no tracking: what reaches inboxes and gets
answered.

What we sell (docs/SERVICES.md): the front desk a small clinic cannot staff - a receptionist that answers every call
and WhatsApp message, books the visit, reminds the patient, and follows up the review visits the doctor advised.

Each kind of practice gets its own words (GROUPS). Every e-mail is put together from a few interchangeable
sentences, chosen per practice by its key, so a practice always gets the same wording while two practices rarely
get identical e-mails (identical mass mail is what spam filters look for).

A text can be replaced in config/outreach.toml under [texts] (first, follow_ups, subjects, footer, auto_reply,
whatsapp_cold, whatsapp_opted_in) and [hooks] (pain / what per group). Placeholders: PLACEHOLDERS below.

Honesty rules for these texts: no invented numbers or clients, no "guarantee", no medical claims, and the example
sums say "if" (they are sums, not results). Reviews are never offered in these e-mails: in India a doctor may not ask
patients for them (docs/STRATEGY.md), and one wording goes to every country.
"""
from __future__ import annotations

import hashlib
import re
import string

from leadgen.country import PACKS

_WHAT = ("We set that up for your clinic: a receptionist that answers every call and WhatsApp message, day and night, "
         "books the visit into your diary and sends the reminder. {extra} It handles appointments only and never "
         "gives medical advice; anything clinical is passed to you.")

# ----------------------------------------------------------------------------------------------- per practice type
GROUPS: dict[str, dict] = {
    "dental": {
        "audience": "dental clinics", "people": "patients", "topic": "missed calls and patients who do not come back",
        "subjects": ["calls {business} misses", "{business}: patients who miss the next sitting",
                     "a question about {business}"],
        "pain": ["Most dental clinics miss calls while the dentist is with a patient or after closing, and a caller "
                 "who gets no answer usually books somewhere else.",
                 "Patients who are asked to come back for the next sitting or a six-month check usually mean to, and "
                 "many never book."],
        "what": _WHAT.format(extra="Patients you asked to come back for a next sitting or a check are reminded when "
                                   "it is due."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "appointments a month going elsewhere",
    },
    "skin": {
        "audience": "skin and cosmetic clinics", "people": "patients", "topic": "missed calls and unfinished courses",
        "subjects": ["calls {business} misses", "{business}: patients who stop mid-course",
                     "a question about {business}"],
        "pain": ["Most skin clinics miss calls during procedures and after closing, and a new patient who gets no "
                 "answer usually calls the next clinic.",
                 "A course of sittings only works when the patient comes back, and many stop after the second visit "
                 "because nobody reminded them."],
        "what": _WHAT.format(extra="Patients who are due for the next sitting of a course you planned are reminded "
                                   "in time."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "consultations a month going elsewhere",
    },
    "eye": {
        "audience": "eye clinics", "people": "patients", "topic": "missed calls and review visits",
        "subjects": ["calls {business} misses", "{business}: review visits that are never booked",
                     "a question about {business}"],
        "pain": ["Most eye clinics miss calls while the doctor is examining or operating, and a caller who gets no "
                 "answer usually books somewhere else.",
                 "Patients who are asked to come back after a procedure or for a yearly check often forget, and "
                 "nobody at the desk has the time to call each of them."],
        "what": _WHAT.format(extra="Patients you asked to return for a review or a yearly check are reminded when it "
                                   "is due."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "appointments a month going elsewhere",
    },
    "women": {
        "audience": "women's health and fertility clinics", "people": "patients",
        "topic": "missed calls and follow-up visits",
        "subjects": ["calls {business} misses", "{business}: follow-up visits that are never booked",
                     "a question about {business}"],
        "pain": ["A first call to a women's health or fertility clinic is often a hard one to make, and a patient "
                 "who gets no answer may not try again.",
                 "Most clinics miss calls while the doctor is in consultation or in theatre, and follow-up visits "
                 "the doctor asked for slip when nobody reminds the patient."],
        "what": _WHAT.format(extra="Patients are reminded, discreetly and without any medical detail in the message, "
                                   "of the follow-up visit you asked for."),
        "math": "if {business} misses 3 calls a day and only 1 of them would have booked, that is about 25 "
                "consultations a month going elsewhere",
    },
    "physio": {
        "audience": "orthopaedic and physiotherapy clinics", "people": "patients",
        "topic": "missed calls and unfinished treatment plans",
        "subjects": ["calls {business} misses", "{business}: patients who stop mid-treatment",
                     "a question about {business}"],
        "pain": ["Most clinics miss calls while the doctor or therapist is with a patient, and a caller who gets no "
                 "answer usually books somewhere else.",
                 "A treatment plan of several sessions only helps when the patient finishes it, and many stop "
                 "halfway because nobody followed up."],
        "what": _WHAT.format(extra="Patients are reminded of the next session of the plan you set and of the review "
                                   "visit you asked for."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "appointments a month going elsewhere",
    },
    "doctor": {
        "audience": "doctors' clinics", "people": "patients", "topic": "missed calls and review visits",
        "subjects": ["calls {business} misses", "{business}: the phone during hospital hours",
                     "a question about {business}"],
        "pain": ["Many doctors run their own clinic around hospital hours, and nobody answers the clinic phone while "
                 "they are on the ward or in theatre.",
                 "Most clinics miss calls during consultations and after closing, and patients who are told to come "
                 "back in two weeks often do not book."],
        "what": _WHAT.format(extra="Patients you asked to come back for a review are reminded when it is due."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "consultations a month going elsewhere",
    },
    "default": {
        "audience": "clinics", "people": "patients", "topic": "missed calls and review visits",
        "subjects": ["calls {business} misses", "{business}: review visits that are never booked",
                     "a question about {business}"],
        "pain": ["Most clinics miss calls while the front desk is busy and after closing, and a caller who gets no "
                 "answer usually books somewhere else.",
                 "Patients who are told to come back for a review usually mean to, and many never book because "
                 "nobody reminded them."],
        "what": _WHAT.format(extra="Patients the doctor asked to come back are reminded when the visit is due."),
        "math": "if {business} misses 4 calls a day and only 1 of them would have booked, that is about 25 "
                "appointments a month going elsewhere",
    },
}

# Our category keys (config/shared/categories.toml) -> the wording group.
_GROUP_WORDS = {
    "dental": ("dental", "dentist", "orthodont"),
    "skin": ("skin", "derma", "cosmetic", "hair"),
    "eye": ("eye", "ophthal", "vision"),
    "women": ("fertility", "women", "gyn", "ivf", "matern"),
    "physio": ("ortho", "physio", "spine", "rehab"),
    "doctor": ("doctor", "physician", "pediatric", "paediatric"),
}


def category_group(key: str) -> str:
    k = (key or "").lower()
    for group, words in _GROUP_WORDS.items():
        if any(w in k for w in words):
            return group
    return "default"


# ------------------------------------------------------------------------------------------------- the e-mails
EN = {
    "first": """{greeting}

{intro}

{pain} {what}

{cta}

{sender_first}
{footer}""",
    "follow_ups": [
        """{greeting}

A short follow-up on my note about {topic}. In plain numbers: {math}. You decide what the receptionist may say, you can listen to it before any patient does, and every booking and message is yours to see.

{cta2}

{sender_first}
{footer}""",
        """{greeting}

Last note from me. If this is not a priority for {business} right now, no problem at all, and I won't write again. If it is, reply "yes" and I'll send you the two-page overview.

All the best,
{sender_first}
{footer}""",
        """{greeting}

I said I would not write again, so only this: the offer stands whenever the front desk becomes a priority for {business}. A one-word reply is enough.

{sender_first}
{footer}""",
    ],
    "intro_usp": ['I came across {business} and noted this line on your website: "{usp}".',
                  'I was reading about {business}, and this line on your website stayed with me: "{usp}".'],
    "intro_plain": ["I came across {business} while looking at {audience} in {place}.",
                    "I found {business} while going through {audience} in {place}.",
                    "{business} came up while I was looking at {audience} in {place}."],
    "intro_noplace": ["I came across {business} while looking at {audience}.",
                      "{business} came up while I was looking at {audience}."],
    "cta": ['Would it be worth sending you a two-page overview? A one-word "yes" is enough.',
            'Shall I send you a two-page overview of how it works? Just reply "yes".',
            'Would a two-page overview be useful? A reply with "yes" is all it takes.'],
    "cta2": ['Shall I send the two-page overview? A "yes" is enough.',
             'Would you like the two-page overview? Just reply "yes".'],
    "greeting_named": ["Hi {first_name},"],
    "greeting_team": ["Hello,", "Hi there,", "Hello {business} team,"],
    # The end of every e-mail. US and Canadian law ask for the sender's postal address and a way to say no in every
    # sales e-mail; the UK and EU ask to say who writes, where the address came from and how to object.
    "footer": """{sender_business}{phone_line}
{address_line}{source_line}Not interested? Reply "no" and I won't write again.""",
    "source_line": 'I found this address on your website or public listing; reply "delete" and I erase it. ',
    "offer_line": "This e-mail is a business offer from {sender_business}. ",
    # To a business that answered "yes" / "send details": the overview, at once, in the same conversation.
    "auto_reply": """{greeting}

Thanks for getting back to me. The two-page overview is attached: what we would set up for {business}, what a call and the reminder messages look like, and how a trial works.

The easiest next step is a 15-minute call.{booking_line} Just reply with a day and time that suits you{whatsapp_line}.

{sender_first}
{sender_business}""",
    "whatsapp_cold": ("Hello {business} team, this is {sender_first} from {sender_business}. We set up a receptionist "
                      "for {audience} that answers every call and WhatsApp message, books the visit and reminds the "
                      "patient. May I send a two-page overview? If you'd rather not hear from us, reply STOP."),
    "whatsapp_opted_in": ("Hi {first_name_or_there}, this is {sender_first} from {sender_business} - thanks for your "
                          "reply to my e-mail about {business}. Happy to answer any questions here, or to set up a "
                          "short call whenever suits you."),
}
LANGS = {"en": EN}

PLACEHOLDERS = {"greeting", "intro", "pain", "what", "math", "topic", "cta", "cta2", "business", "first_name",
                "first_name_or_there", "audience", "people", "place", "usp", "sender_name", "sender_first",
                "sender_business", "sender_phone", "sender_address", "sender_website", "footer", "phone_line",
                "address_line", "source_line", "booking_line", "whatsapp_line"}


class _Keep(dict):
    def __missing__(self, key):          # an unknown {placeholder} stays visible (the lint then refuses the e-mail)
        return "{" + key + "}"


def render(template: str, ctx: dict) -> str:
    text = str(template).format_map(_Keep(ctx))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def unknown_placeholders(template: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(str(template)) if f} - PLACEHOLDERS


def pick(options, seed: str) -> str:
    """The same choice for the same business every time; different businesses get different ones."""
    if isinstance(options, str):
        return options
    if not options:
        return ""
    return options[int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16) % len(options)]


def tidy_address(text: str) -> str:
    """The postal address as typed in the settings, on one line, tidily."""
    parts = [re.sub(r"\s+", " ", p).strip(" ,") for p in re.split(r"[\n,]+", text or "")]
    out = ", ".join(p for p in parts if p)
    return string.capwords(out, " ") if out and out == out.lower() else out


def texts(o: dict, lang: str = "en") -> dict:
    """The language's texts with the owner's replacements ([texts] in config/outreach.toml)."""
    return {**LANGS.get(lang, EN), **{k: v for k, v in (o.get("texts") or {}).items() if v}}


def group_words(o: dict, group: str) -> dict:
    return {**GROUPS["default"], **GROUPS.get(group, {}), **((o.get("hooks") or {}).get(group) or {})}


def context(lead, o: dict, *, mailbox_name: str = "") -> dict:
    """Everything a template can use for one lead. o = the outreach config."""
    pack = PACKS.get(lead.country or "US", PACKS["US"])
    t = texts(o, pack.language)
    s = o["sender"]
    g = group_words(o, category_group(lead.category_key))
    seed = lead.key
    name = (mailbox_name or s.get("name") or "").strip()
    first = lead.first_name
    usp = re.sub(r"\s+", " ", lead.usp or "").strip().rstrip(".!?").replace('"', "'")
    place = (lead.city or lead.area or "").strip()
    address = tidy_address(s.get("postal_address", ""))
    phone = str(s.get("phone") or "").strip()
    ctx = {
        "business": lead.business, "first_name": first, "first_name_or_there": first or "there",
        "audience": g["audience"], "people": g["people"], "topic": g["topic"], "place": place, "usp": usp,
        "sender_name": name, "sender_first": name.split(" ")[0] if name else "",
        "sender_business": str(s.get("business") or "").strip(), "sender_phone": phone,
        "sender_address": address, "sender_website": str(s.get("website") or "").strip(),
        "phone_line": f"\nWhatsApp / phone: {phone}" if phone else "",
        "address_line": f"{address}\n\n" if address else "\n",
        "booking_line": "", "whatsapp_line": f", or message me on WhatsApp: {phone}" if phone else "",
    }
    if s.get("booking_link"):
        ctx["booking_line"] = f" You can pick a time here: {s['booking_link']}"
    ctx["greeting"] = render(pick(t["greeting_named"] if first else t["greeting_team"], seed + "|g"), ctx)
    if usp and 20 <= len(usp) <= 140:
        ctx["intro"] = render(pick(t["intro_usp"], seed + "|i"), ctx)
    else:
        ctx["intro"] = render(pick(t["intro_plain"] if place else t["intro_noplace"], seed + "|i"), ctx)
    ctx["pain"] = render(pick(g["pain"], seed + "|p"), ctx)
    ctx["what"] = render(g["what"], ctx)
    ctx["math"] = render(g["math"], ctx)
    ctx["cta"] = render(pick(t["cta"], seed + "|c"), ctx)
    ctx["cta2"] = render(pick(t["cta2"], seed + "|c2"), ctx)
    rules = pack.rules
    source = t["source_line"] if rules.privacy_notice else (t["offer_line"] if rules.postal_address_required else "")
    ctx["source_line"] = (render(source, ctx) + " ") if source else ""
    ctx["footer"] = render(t["footer"], ctx)
    return ctx


def subject_for(lead, o: dict) -> str:
    pack = PACKS.get(lead.country or "US", PACKS["US"])
    t = texts(o, pack.language)
    options = t.get("subjects") or group_words(o, category_group(lead.category_key))["subjects"]
    return pack.rules.subject_prefix + render(pick(options, lead.key + "|s"), {"business": lead.business})


def first_email(lead, o: dict, *, mailbox_name: str = "") -> tuple[str, str]:
    ctx = context(lead, o, mailbox_name=mailbox_name)
    return subject_for(lead, o), render(texts(o, PACKS.get(lead.country or "US", PACKS["US"]).language)["first"], ctx)


def follow_up(lead, o: dict, n: int, *, mailbox_name: str = "") -> str:
    """The n-th follow-up (1 = the first one)."""
    ctx = context(lead, o, mailbox_name=mailbox_name)
    options = texts(o, PACKS.get(lead.country or "US", PACKS["US"]).language)["follow_ups"]
    return render(options[min(n - 1, len(options) - 1)], ctx)


def auto_reply(lead, o: dict, *, mailbox_name: str = "") -> str:
    ctx = context(lead, o, mailbox_name=mailbox_name)
    return render(texts(o)["auto_reply"], ctx)


def whatsapp_text(lead, o: dict, reason: str) -> str:
    ctx = context(lead, o)
    return render(texts(o)["whatsapp_opted_in" if reason == "opted_in" else "whatsapp_cold"], ctx)
