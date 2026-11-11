# Clinic automation: what to sell, to whom, and what is off-limits

Researched 11 November 2026. Regulatory points come from news and law-firm
summaries found by web search; I could not open the regulators' own documents
from this session, so every rule below needs a read of the primary text (or a
lawyer) before you sign a client. Prices marked "my estimate" are judgment, not
market data.

## Recommendation

**Lead with a "front desk and follow-up" system. Keep review-building out of the
India offer entirely.**

One product, three parts, sold together:

1. **AI receptionist** on the clinic's WhatsApp number and missed calls: answers
   hours, fees, location and doctor availability, books and reschedules, and hands
   anything clinical to a human.
2. **Reminders and doctor-advised follow-ups**: appointment reminders, and a
   message when a review visit the doctor asked for is due or was missed.
3. **A daily sheet for the doctor**: patients seen, follow-ups due this week,
   follow-ups missed, calls caught after hours.

Why this one: it is care administration rather than advertising, so it survives
the strictest rules in every market checked; the pain is measurable (vendor
studies put unanswered calls at 20-38% of incoming calls in dental practices,
though none traced to a primary study); and part 3 is the tracking you described,
produced as a by-product of parts 1 and 2.

## Your five ideas, checked

| Idea | India | US / UK | Australia / Singapore |
|---|---|---|---|
| Build Google reviews | **No** for doctors. NMC guidelines of 6 Oct 2026 reportedly bar a doctor from requesting or sharing patient reviews for promotion, and cover agencies acting for them. Dentists: a 14 Oct 2026 National Dental Commission advisory warns on solicitation; clause text not read, so treat as no. | Yes, with Google's rules: ask every patient, never only the happy ones, no reward of any kind, no staff quotas. | Avoid. Testimonials in health advertising are banned (AHPRA; Singapore PHMC rules and SMC code). |
| Post-visit follow-up check | Yes | Yes | Yes |
| Message past patients for a new check-up | Only when the doctor advised that review. A blanket "time for a check-up" campaign is solicitation. | Reminders tied to care: yes. Promotional texts need written consent (TCPA), plus HIPAA authorization if they use health details. | Care reminders only |
| AI receptionist | Yes | Yes | Yes |
| Patient and follow-up tracking | Yes | Yes | Yes |

Two things the receptionist must never do, anywhere: give medical advice or
triage symptoms (it books and escalates), and pose as a patient or write review
text. The NMC guidelines also reportedly bar AI-made content that misrepresents
diagnosis, outcomes or patient experience.

## Patient data: the rules the product has to follow

- The clinic owns the patient data; you only process it on the clinic's
  instructions. Put that in the contract.
- **India (DPDP Act and Rules):** rules notified 13 Nov 2025, with full
  compliance reported as due around May 2027. Consent must be specific and
  itemised; blanket consent does not count. Build a consent line into the
  clinic's registration step and store the timestamp.
- **WhatsApp:** use the official Business API with patient opt-in. Reported India
  rates are about Rs 0.12-0.15 per utility message (reminders) and Rs 0.86-1.09
  per marketing message; sources disagree, so check Meta's rate card.
- **US:** a signed business associate agreement with the clinic before touching
  any patient record; appointment reminders count as treatment communication.
- Encrypt stored data, keep it in one place, and delete on request.

## Who to sell to

Best first buyers, in order:

1. **Hospital consultants with their own evening clinic.** Nobody answers the
   clinic phone while they are at the hospital. This is the group you asked me to
   dig out, and the cross-match tool in this project is built for it.
2. **Owner-run dental, skin/cosmetic, eye, orthopaedic/physio and fertility
   clinics** with one to three doctors: one extra kept appointment pays for a
   month.
3. Skip chains (they buy centrally) and general-practice clinics with low fees.

## Price (my estimate, untested)

Anchors found: US dental AI receptionists run about $150-$1,500 a month per
location (Weave from about $199-249, Podium from about $399); Indian clinic
software lists at about Rs 1,000-13,000 a month.

| Market | Setup | Monthly |
|---|---|---|
| India, high-value specialty clinic | Rs 25,000-40,000 | Rs 8,000-15,000 |
| US / UK / Gulf, dental or cosmetic | $1,000-2,500 | $400-900 |

High ticket is realistic abroad and for Indian specialty clinics. It is not
realistic for a neighbourhood GP clinic. You have no case study yet, so the first
three clients should be discounted pilots in exchange for before/after numbers.

## Order of work

1. Pull leads (this project) for Kolkata and New Delhi, then one foreign capital.
2. Build the receptionist + reminder product for one clinic type (dental).
3. Run three pilots you can visit in person. As a medical student you can walk
   into clinics and talk to doctors as a junior colleague; no agency abroad can.
4. Sell abroad with the pilot numbers. Add the review request step only for US
   and UK clients.

## Not researched yet

- Rules for cold-contacting clinics themselves (email, calls, WhatsApp) in each
  country. Cold WhatsApp messages to businesses break WhatsApp's terms; plan on
  email, phone and visits.
- UAE, Canada, Ireland, New Zealand and the other capitals in `config/cities.csv`
  are marked `check`: no review rule was confirmed either way.
- Exact NMC penalty wording; sources conflict (warning and training, up to
  removal from the register for one to three years).

## Sources

- NMC guidelines, Oct 2026: [Medical Dialogues](https://medicaldialogues.in/health-news/nmc/nmc-issues-ethical-advertising-public-communication-guidelines-for-doctors-hospitals-details-180731), [testimonials and third parties](https://medicaldialogues.in/health-news/nmc/doctors-cannot-use-celebrities-influencers-patients-to-promote-professional-services-through-prohibited-testimonials-endorsements-nmc-181199), [The South First](https://thesouthfirst.com/health/doctors-on-instagram-nmc-says-no-to-patient-testimonials-paid-ads-ai-promotions-and-guaranteed-claims/), [guideline PDF](https://medicaldialogues.in/pdf_upload/2026/10/07/nmc-guidelines-on-ethical-advertising-and-public-communication-478642.pdf), [Ichelon](https://ichelonconsulting.com/insights/nmc-2026-ethics-code-complete-guide-doctors)
- National Dental Commission advisory: [Medical Dialogues](https://medicaldialogues.in/news/health/doctors/national-dental-commission-warns-dentists-against-unethical-social-media-advertising-181335), [NDC replaces DCI](https://www.clearhq.org/news/india-establishes-new-national-dental-commission-3-25-26)
- Google review rules: [Mainstreethost](https://www.mainstreethost.com/blog/google-review-policy-update-april-2026/), [DAC Group](https://www.dacgroup.com/?p=159133), [Search Lab](https://searchlabdigital.com/blog/google-review-guidelines-2026-update/)
- DPDP: [KPMG healthcare paper](https://assets.kpmg.com/content/dam/kpmgsites/in/pdf/2025/12/the-privacy-prescription-impact-of-dpdp-act-and-rules-in-healthcare-and-life-sciences-sector.pdf.coredownload.pdf), [Cyril Amarchand alert](https://www.cyrilshroff.com/wp-content/uploads/2025/11/Client-Alert-DPDP-Rules-Nov-2025.pdf), [Mondaq](https://www.mondaq.com/india/data-protection/1706890/a-closer-look-at-the-dpdp-rules-2025)
- WhatsApp pricing: [MyOperator](https://myoperator.com/blog/whatsapp-business-api-pricing-india-2026), [AiSensy](https://m.aisensy.com/blog/whatsapp-per-message-pricing-update-effective-january-1-2026/), [baat.ai](https://baat.ai/blog/whatsapp-api-pricing-india)
- Australia / Singapore: [AHPRA testimonial tool](https://www.ahpra.gov.au/resources/advertising-hub/resources-for-advertisers/testimonial-tool.aspx), [Singapore MOH Q&A](https://ask.gov.sg/moh/questions/clu6lx3rk009q314rqjdwzfmj), [SMC caution on rating platforms](https://www.globalcompliancenews.com/2021/01/18/singapore-doctors-strongly-cautioned-not-to-participate-in-platforms-that-use-patient-feedback-and-ratings29122020/)
- UK: [GDC advertising guidance](https://gdc-uk.org/standards-guidance/standards-and-guidance/gdc-guidance-for-dental-professionals/guidance-on-advertising), [British Dental Journal paper](https://www.nature.com/articles/s41415-022-4977-0)
- US texting: [Medical Economics](https://www.medicaleconomics.com/view/texting-patients-hipaa-tcpa-carrier-rules-every-practice-must-follow), [Foley](https://www.foley.com/p/102kcrt/the-intersection-of-ai-digital-health-and-the-tcpa-what-you-need-to-know/)
- UAE: [Gulf News on DHA rules](https://gulfnews.com/uae/health/dubai-issues-social-media-rules-for-doctors-health-facilities-and-influencers-bans-misleading-claims-1.500659503)
- Prices and missed calls: [eesel](https://www.eesel.ai/blog/ai-receptionist-for-dentists), [Dentalbase](https://www.dentalbase.ai/blogs/ai-dental-receptionist-cost-2026-pricing-breakdown), [Quo on Weave](https://www.quo.com/blog/weave-pricing/), [Clinizy on SaaSworthy](https://www.saasworthy.com/product/clinizy-care/pricing), [Dental Economics](https://www.dentaleconomics.com/practice/article/55385634/the-economics-of-missed-calls-quantifying-revenue-loss-in-dental-practices), [Solutionreach](https://www.solutionreach.com/guide/resources-missed-calls-cost-guide)
