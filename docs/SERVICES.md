# What we offer a clinic

The list to walk a doctor through. Each service is shown working in the demo
(`demo/`, published as the "Clinic Front Desk" page), on invented patients.

| # | Service | What the clinic gets | Where it may be sold |
|---|---|---|---|
| 1 | **Receptionist that never misses a call** | A voice and WhatsApp assistant that answers day and night, gives hours, fee and address, books, changes and cancels appointments, writes the patient's name, number, time and reason into the diary, and passes anything clinical to a person. | Everywhere |
| 2 | **Reminders** | A confirmation at booking and a reminder before the visit, on WhatsApp or e-mail. The patient confirms or changes the time by replying. | Everywhere |
| 3 | **Follow-ups the doctor asked for** | When the doctor advises a review visit, the patient is reminded when it is due and rebooked. A missed visit gets a new time offered. | Everywhere |
| 4 | **Post-visit check** | The day after a procedure the patient is asked how they are; a reply asking for help reaches the clinic at once. | Everywhere |
| 5 | **Google reviews** | The same polite request to every patient the day after a visit, no reward, nothing about the treatment. | US and UK. **Not India, Australia or Singapore** (see STRATEGY.md); there patients get a private feedback question instead. Other countries: check first. |
| 6 | **The doctor's daily sheet** | Patients seen, who did not come, follow-ups due and overdue, calls caught after hours, messages sent. | Everywhere |
| 7 | **A website for the clinic** | A fast, clear site: doctors, timings, location, fees and a booking button. Set up and looked after for the clinic. | Everywhere |

Other things the same system can do once a clinic is live, if a doctor asks:
a waiting list that fills cancelled slots, a reminder to collect reports,
vaccination and recall schedules the doctor sets, payment reminders, and the
same assistant on the clinic's website chat.

## What the assistant will not do

- Give medical advice, suggest medicines or triage symptoms. It offers the
  earliest appointment, and sends emergencies to the nearest emergency department.
- Send general "come for a check-up" promotions to past patients. Only visits
  the doctor advised are followed up.
- Write or post a review, pick only happy patients to ask, or offer a reward.

## "Training" the voice agent

It is not trained like a student. It is given the clinic's facts and rules in
writing (hours, fees, doctors, what to do in an emergency, what never to say)
and connected to the clinic's diary. The demo's instructions are in
`demo/engine.js` (`rules`), and its abilities are the five tools beside them
(look up free times, book, find, cancel, take a message). Setting up a new
clinic means editing those facts, then testing with twenty or so pretend calls.

## What each service needs before it runs for a real clinic

| Service | Needs | State today |
|---|---|---|
| Voice calls | A phone number that forwards to a voice-AI platform (speech in, speech out) given the clinic's facts and the booking tools. Indian platforms (Bolna, Ringg, Bolti and others) quote about Rs 4-8 a minute with Hindi and Bengali, plus about Rs 500 a month per number; vendor figures, unchecked. | Demo only: talks in the browser, no phone line yet |
| WhatsApp messages | The clinic's own number on the WhatsApp Business API (through Meta or a provider), approved "utility" templates for reminders, patient opt-in. Reported cost about Rs 0.12 per reminder; vendor figure. | Not built: messages go by e-mail for now |
| E-mail messages | The clinic's mailbox, or ours on its behalf (`cg clinic`) | **Built** (`clinicreach/patients.py`): reminders, follow-ups, rebooking, post-visit check, feedback; tested on a demo clinic, never sent to a real patient |
| Diary | Either our own diary (as in the demo) or the clinic's export as `patients.csv` | The patient list is read from the clinic's export; no live link to clinic software |
| Patient data | A signed agreement with the clinic, consent wording at registration, storage in one protected place | Consent column enforced; agreement not drafted yet; required before any real patient is loaded |
| Website | A domain in the clinic's name and a host (GitHub Pages is free) | Not built yet |

## Try the patient messages yourself (tablet)

```
cg clinic demo
cg clinic preview demo
cg clinic run demo --to yourown@gmail.com
cg clinic sheet demo
```

The first line makes a demo clinic with 10 invented patients. The second shows what each would get. The
third sends every one of those messages to your own address, marked TEST, so you see exactly what a patient
sees. The last prints the doctor's morning sheet. `cg clinic demo us-demo --country US` makes one in the US,
where the feedback message becomes a Google review request.

Sources for the costs above: [Vyora](https://www.vyora.ai/best-ai-voice-agent-india),
[caller.digital](https://caller.digital/blog/voice-ai-india-2026-complete-guide),
[Bolti](https://bolti.co.in/blog/voice-ai-platform-pricing-india-comparison),
[Trikon](https://www.trikon.tech/voice-pricing-comparison),
[RichAutomate](https://richautomate.in/blog/whatsapp-for-healthcare-clinics-india-2026),
[D7 Networks](https://d7networks.com/whatsapp-business-api/whatsapp-message-templates/utility-templates/utility-templates-for-healthcare/).
