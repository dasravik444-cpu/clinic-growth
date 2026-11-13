# Working on this repository (read first)

The owner is a medical student, not a programmer, and talks to you from a phone. Give exact commands,
one per line, and say what each does. Straight answers, no padding. Say plainly what was tested and
what was not.

- This project is separate from worldreach, plant-parlour and agency-lead-lab. Do not mix data or
  settings with them. `leadgen/` is a copy of worldreach's lead finder: when a fix is made in one,
  consider the other.
- The repository is public. Never commit lead data, rosters, patient data, keys, or the owner's
  phone, address or e-mail.
- Review requests are sold only where the regulator allows them (`review_offer` in
  `config/cities.csv`, `REVIEW_RULES` in `demo/engine.js`, docs/STRATEGY.md). They are off for India.
  Do not build ways around that, fake reviews, review gating or rewards.
- The assistant never gives medical advice. Keep that rule in `rules()` in `demo/engine.js`.
- No real patient data until a clinic has signed an agreement and patients have consented.
- WhatsApp is never automated from a personal number; only the official Business API with opt-in.
- Tests: `python -m pytest -q` and `node --test demo/engine.test.js`.
- Leads from a Claude cloud session: `python scripts/cloud_leads.py fetch`, then `run --all`, then
  `python -m clinicleads shortlist`. It needs only the Overture Maps storage host, which the default
  network already allows. Clinic websites cannot be read from a cloud session, so e-mails found only
  on websites need the tablet (`python -m clinicleads find CITY`). Hand lead files to the owner as
  files; never commit them.
- The demo is published as the artifact "Clinic Front Desk"
  (https://claude.ai/artifact/Pk8LMPRGUZnJUJR86wxwjS). To update it, publish `demo/index.html` with
  `demo/engine.js` to that URL; do not create a second page.
