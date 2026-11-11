# Clinic Growth

Lead collection for selling front-desk and follow-up automation to doctors'
clinics, dental clinics and other small practices. Separate from the Plant
Parlour and agency projects; shares no code or data with them.

- What to sell and what the rules allow: [docs/STRATEGY.md](docs/STRATEGY.md)
- Python 3.11+, standard library only (`openpyxl` only if you want `.xlsx`).

**Status, 11 Nov 2026:** the code passes 17 offline tests on invented data. It
has never completed a live run: the session it was written in could not reach any
of the data sources. No real leads have been collected yet. The first run on an
open network is the real test.

## Run it (tablet or any computer)

```bash
cd clinic-growth
python -m unittest discover -s tests -t .          # should say OK

python -m clinicleads collect --city "Kolkata" --city "New Delhi"
python -m clinicleads collect --country IN          # every Indian capital in the list
python -m clinicleads collect --all                 # all 38 cities, about 10 minutes
python -m clinicleads npi --city Washington --state DC   # US clinicians, public registry

python -m clinicleads enrich --limit 300            # read clinics' own sites for emails
python -m clinicleads stats
python -m clinicleads export data/leads.xlsx --min-score 40
```

Cities live in `config/cities.csv`; add a row to add a city. The `review_offer`
column records whether a review-request service may be pitched there
(`restricted`, `allowed-with-rules`, or `check` = not yet researched).

## Where the leads come from

| Source | Covers | Gives |
|---|---|---|
| OpenStreetMap (Overpass) | every city | clinics, dentists, doctors, hospitals; phone/site/email where published |
| US NPI Registry | United States | each licensed clinician, practice address and phone |
| The clinic's own website | any lead with a site | emails, phones, WhatsApp links, only where robots.txt allows |

Every lead keeps the URL it came from. Nothing is guessed or filled in by a
model. OpenStreetMap is thin in parts of India; if a city comes back small, the
Overture Maps source used in Plant Parlour v2 is the next provider to add.

## Hospital doctors with their own practice

1. `python -m clinicleads hospitals` lists the hospitals found, with websites.
2. Read each hospital's "our doctors" page into a roster file shaped like
   `rosters/EXAMPLE.csv`. This is the slow manual part; Claude can do it in a
   session that is allowed to open those sites.
3. `python -m clinicleads crossmatch rosters/kolkata.csv` marks clinics named
   after a rostered doctor. `strong` = first name and surname both match;
   `weak` = surname and initial. Two doctors can share a name, so confirm each
   match before contacting anyone.
4. `python -m clinicleads export data/consultants.csv --consultants`

For the US, the `npi` command flags clinicians who file more than one practice
location, which is the same signal.

## Score

0-100, with the reasons written next to it: phone +25, email +20, website +15,
owner-named practice +15, high-value specialty +15, hospital consultant with own
practice +15, hours listed +5, WhatsApp link +5, chain -30, no contact route -20.
Hospitals are kept only as roster sources and always score 0.
