# Clinic Growth

Front-desk and follow-up automation for doctors' clinics and dental clinics, and
the lead finder to sell it. Separate from WorldReach, Plant Parlour and the
agency projects; it shares no data with them.

| Part | What it is | State |
|---|---|---|
| **Demo** (`demo/`) | The product on invented patients: an AI receptionist you can talk to, the appointment diary, reminders, doctor-advised follow-ups, review rules by country, the doctor's daily sheet. Published as the "Clinic Front Desk" page. | Works. Logic covered by 10 tests; the page was run in a browser with the scripted receptionist. The Claude voice path only runs inside the published page. |
| **Lead finder** (`leadgen/`) | The WorldReach lead finder, copied here: open map data (Overture Maps, OpenStreetMap), each practice's own website, e-mail hunt, Google Sheet. Set up for 8 kinds of medical practice in 27 capital cities. | 97 tests pass. Run for real on 13 Nov 2026 from open map data: 61,025 clinics in the 27 cities, 29,538 with e-mail. Website reading has not run for clinics yet. |
| **Sending** (`clinicreach/`, command `cg`) | The WorldReach sending engine, copied here: Gmail, Outlook and own-domain mailboxes with warm-up and brakes, follow-ups, replies, the Google Sheet, the WhatsApp queue, the robot's timetable, the overview PDF. Clinic wording, no review offers, hospitals never written to. | 37 tests pass against pretend mailboxes and a pretend Sheet. **Has not sent a real e-mail or touched a real Sheet from this project.** |
| **Shortlist** (`clinicleads/`) | Scores the clinics, and finds hospital doctors who run their own clinic by matching hospital "find a doctor" listings to clinics named after the same doctor. | 10 tests pass; run on the real lists. Matches are candidates to confirm. The US registry reader has never run live. |

| Read | For |
|---|---|
| [docs/SERVICES.md](docs/SERVICES.md) | the list of services to pitch, and what each needs to go live |
| [docs/STRATEGY.md](docs/STRATEGY.md) | what to sell where, prices, and the rules (reviews are off in India) |
| [docs/SETUP.md](docs/SETUP.md) | **the tablet, step by step**: install, Google Sheet, Gmail and Outlook mailboxes, first e-mails |
| [docs/OUTLOOK.md](docs/OUTLOOK.md), [DELIVERABILITY](docs/DELIVERABILITY.md), [COMPLIANCE](docs/COMPLIANCE.md), [WHATSAPP](docs/WHATSAPP.md), [HOSTING](docs/HOSTING.md) | Outlook sign-in, staying out of spam, the rules per country, the WhatsApp number, tablet or server |

## The demo

Open the published page, or locally: put `demo/index.html` and `demo/engine.js`
in one folder and open the HTML file. Tests: `node --test demo/engine.test.js`

- Talk to the receptionist as a patient; the booking appears in the Diary.
- "+1 hour" and "Next morning" move the demo clock, and the system sends what
  is due by itself.
- Reviews: change the country to see the request switch on or off.

Inside Claude the receptionist is Claude itself and can listen and speak (in
Chrome or the desktop app). Anywhere else a simple scripted receptionist answers.

## On the tablet: one command, `cg`

```
cg on / cg off        the robot (e-mails hourly in clinic hours, a lead search every evening)
cg status             mailboxes (warm-up, pauses), leads, e-mails, replies
cg check              test the settings, the Sheet, every mailbox and our own e-mails
cg preview dental     show the e-mails a dental clinic would get
cg leads              find clinics in the next city now, into the Google Sheet
cg test a@x b@y       spam test: the next first e-mail from every mailbox, only to your own addresses
cg emails --dry-run   prepare the e-mails into the Sheet's "Email Preview" tab, send nothing
cg report             e-mails per day, bounces, replies, who is waiting for your answer
```

Setup is in docs/SETUP.md. It has its own Ubuntu, folder and job number, so the other robots are not touched.

## Finding leads by hand (any computer with open internet)

```bash
pip install -r requirements.txt
python -m clinicleads cities                   # the 27 cities
python -m clinicleads find kolkata --no-sheets # one run = one half of the city; run again for the rest
python -m clinicleads status kolkata
python -m clinicleads export kolkata           # writes data/leads-kolkata.csv
```

Leave out `--no-sheets` to write to a Google Sheet (same setup as WorldReach:
`WR_SHEET_ID` and the service-account key). A lead needs a phone, e-mail or
WhatsApp number to qualify. Every contact keeps the page it came from; nothing
is guessed.

Add a city: add a row to `config/cities.csv`, then `python scripts/make_markets.py`.

### The working list

```bash
python -m clinicleads shortlist    # every exported city -> data/clinic-leads.xlsx
```

| Sheet | What it holds |
|---|---|
| Summary | counts per city |
| Clinics | practices to pitch, best first. Score: e-mail 30, phone 25, own website 15, owner-named 15, high-value field 15 |
| Consultants | clinics named after a doctor who is also listed on a hospital's site |
| Rosters | the hospital listings behind those matches (the phone there is the hospital's) |
| Hospitals | hospitals found (not leads) |

`Contact Rule` says how a business in that country may be contacted; `Review offer`
says whether the review service may be pitched there.

### From a Claude cloud session

A cloud session cannot use the normal download or read clinic websites. This does
the open-map-data part there:

```bash
python scripts/cloud_leads.py fetch      # about 550 MB for the 27 cities
python scripts/cloud_leads.py run --all
python -m clinicleads shortlist
```

### Hospital doctors with their own practice

```bash
python -m clinicleads hospitals kolkata                       # hospitals found, with websites
# read each hospital's "our doctors" page into rosters/kolkata.csv:
#   doctor_name,specialty,hospital,source_url
python -m clinicleads consultants kolkata rosters/kolkata.csv # writes data/consultants-kolkata.csv
python -m clinicleads npi Washington DC                       # US: clinicians filing more than one practice
```

A clinic named after a rostered doctor is a candidate: `strong` when first name
and surname both match, `weak` on surname and initial. Two doctors can share a
name, so confirm each one before contact.

## Never in git

This repository is public. Lead data, rosters, patient data, keys and settings
stay out of it (`.gitignore`).

Contains data from the Overture Maps Foundation (CDLA-Permissive-2.0) and
© OpenStreetMap contributors (ODbL) once the lead finder has run.
