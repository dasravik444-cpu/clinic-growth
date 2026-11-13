# The rules, per country

A working summary, taken over from WorldReach (10 November 2026) and extended for clinics on 13 November 2026.
**Not legal advice.** The US, UK and Ireland parts rest on regulators' own pages; the India row is Claude's
understanding and has not been checked by a lawyer; the rest of Europe rests on secondary sources that partly
contradict each other. Before a large campaign in a new country, have a local lawyer check one e-mail.

This page is about writing to **clinics** (business to business). What a clinic may send to its own **patients**,
and where reviews may be asked for, is in docs/STRATEGY.md.

## 1. Where a business may be e-mailed without having asked

| Country | First e-mail to a business | What every e-mail needs | In Clinic Growth |
|---|---|---|---|
| **India** | No anti-spam law for e-mail. The data-protection act (DPDP Act 2023, s. 3(c)(ii)) leaves out contact details a person has made public themselves, which is what the lead finder collects. Unverified by a lawyer. | Who writes, a way to say no | on (`in`), the default market |
| **United States** | Allowed (CAN-SPAM is an opt-out law, also for businesses) | Truthful sender and subject, **your postal address**, a way to say no that is honoured within 10 business days | on (`us`) |
| **United Kingdom** | Only **limited companies** (Ltd, LLP, PLC). Sole traders and partnerships need consent (PECR reg. 22) | Who writes, a way to say no; where the address came from (UK GDPR Art. 14) | on (`gb`): only leads whose website shows a company form are e-mailed |
| **Ireland** | Only **companies** (Ltd, DAC, PLC), about their business; sole traders need consent | as the UK | on (`ie`), same rule (Dublin) |
| Canada | Only an address the business **publishes itself**, about its business (CASL implied consent) | Your name, postal address, unsubscribe | on (`ca`), Ottawa |
| Australia, New Zealand | Only a conspicuously **published** business address, relevant message | Who writes, unsubscribe | city files exist (`au`, `nz`); Australia has an open question on collecting addresses by software - ask before switching it on |
| **France** | Allowed to professional addresses when the offer concerns the person's job; opt-out (CNIL) | Who writes, where the address came from, a free and simple way to object | not built: needs French e-mails |
| **Sweden**, Finland | Reported allowed to legal persons (companies), not to sole traders | Who writes, opt-out | not built: needs company-form detection (AB, Oy) |
| Belgium, Portugal | Reported allowed to companies' impersonal addresses (info@) | Who writes, opt-out | not built |
| **Netherlands** | Consent, unless the business published the address for the purpose of being offered things; the regulator reads this narrowly, and sole traders count as persons | | treat as consent only |
| **Germany**, Austria, Switzerland | **Not allowed** without prior consent, businesses included (Germany: UWG § 7; competitors send paid warning letters) | | never e-mailed |
| **Spain, Italy, Poland, Denmark** | Consent required, businesses included | | never e-mailed |

So "Europe" starts with the **UK and Ireland**: English, clear rules, and built. France and Sweden are the next
candidates. Most of the rest of the EU cannot be cold e-mailed lawfully; there the way in is being found
(a website, a listing) or a first contact by letter.

`leadgen/country.py` holds each country's rule; the engine applies it to every lead by its own country
(`clinicreach/outreach/engine.py`, `_pick`), and the summary of each run says how many leads were left out by rule.

## 2. What the code enforces

| Rule | Where |
|---|---|
| Postal address in every US e-mail (sending refuses to start without POSTAL_ADDRESS) | `Engine._sender_problem`, footer in `templates.py` |
| UK / Ireland: e-mail only companies | `Engine._pick` with the lead's Legal Form |
| Where the address came from + "reply delete" (UK, Ireland) | footer in `templates.py` |
| A business whose website says "no unsolicited offers" is skipped | lead finder (`no_marketing_notice`), `Engine._pick` |
| "No" / "stop" / "unsubscribe" / a bounce ends all contact, from every mailbox | `Engine._inbox_event`, the Do Not Contact tab |
| Only addresses the business published; nothing guessed | lead finder; `include_unverified = false` |
| Truthful subject and sender; no disguise | `templates.py`; mail goes out under your own name from your own mailbox |
| WhatsApp never automated | `android/whatsapp.sh` (you press Send) |

## 3. Clinics are not ordinary businesses

- **We write to the clinic, never to its patients.** Nothing in this project sends anything to a patient. That part
  starts only with a signed agreement with the clinic and patients' consent (docs/SERVICES.md).
- **Hospitals are never written to.** They are in the Sheet for the hospital-doctor search. A hospital's own
  "find a doctor" listing is skipped as well: its phone and e-mail are the hospital's (`Engine._practices_only`).
- **No e-mail offers reviews.** In India a doctor may not ask patients for them (NMC guidelines, 6 October 2026),
  and one wording goes to every country (`tests/reach/test_mail.py` checks every text).
- **No medical claims** in any e-mail, and no numbers presented as results: the sums say "if".
- **Singapore and the United Arab Emirates** have city files but are not in the default markets; their rules for
  cold e-mail were not researched. Check before adding `sg` or `ae` to MARKETS.
- **US clinics:** writing to them is ordinary business e-mail. Handling their patient lists later needs a signed
  HIPAA business associate agreement first.

## 4. Sources

- US: [FTC, CAN-SPAM Act: a compliance guide for business](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business); [FTC rule on consumer reviews, 16 CFR 465](https://www.ftc.gov/business-guidance/resources/soliciting-paying-online-reviews-guide-marketers)
- UK: [ICO, business-to-business marketing](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/); [CMA guidance on fake reviews, CMA208](https://gov.uk/government/publications/fake-reviews-cma208)
- Germany: [UWG § 7](https://www.gesetze-im-internet.de/uwg_2004/__7.html)
- Google: [Maps user-contributed content policy](https://support.google.com/contributionpolicy/answer/7400114)
- Rest of Europe (secondary, partly contradictory; verify before use): [ediware, B2B cold e-mailing legal framework](https://www.ediware.eu/b2b-email-marketing/b2b-cold-emailing-legal-framework/); [dotsland, B2B cold email rules by country](https://dotsland.com/en/b2b-cold-email-europe-by-country/); [Dealfront, cold calling and e-mailing laws in Europe](https://www.dealfront.com/guides/guide-to-cold-calling-and-emailing-europe); [overloop (Netherlands)](https://overloop.com/nl/blog/koude-acquisitie-wetgeving); [lawline.se (Sweden)](https://lawline.se/answers/kravs-samtycke-for-att-skicka-e-post-i-marknadsforingssyfte-till-person-pa-annat-foretag)
- Microsoft's sign-in change for Outlook: [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5837174/smtp-information-for-outlook); Exchange Online SMTP AUTH timeline: [Message Center MC786329](https://mc.merill.net/message/MC786329)
