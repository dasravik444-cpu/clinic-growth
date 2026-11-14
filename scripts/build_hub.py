"""Build the Demo Room page (demo/hub-template.html) from the real code: the e-mails clinics get, the patient
messages of the demo clinic, the morning sheet, both brochures, and the lead counts.

    python scripts/build_hub.py OUT_DIR [LEADS_DIR]

OUT_DIR gets index.html plus the brochure page images and PDFs to publish beside it. LEADS_DIR holds the lead
finder's exports (leads-<city>.csv or <city>.csv); without it the leads table shows the counts of 13 Nov 2026.
Published as the artifact "Clinic Growth Demo Room" (https://claude.ai/artifact/NSDG1RYKT2VDGGS4CbsriZ):
republish OUT_DIR/index.html with the images and PDFs as files, to that URL.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from clinicleads import crossmatch as cm  # noqa: E402
from clinicleads import shortlist as sl  # noqa: E402
from clinicreach.outreach import config as C  # noqa: E402
from clinicreach.outreach import templates as T  # noqa: E402
from clinicreach.outreach.leads import Lead  # noqa: E402
from clinicreach.patients import Clinic, make_demo  # noqa: E402

KINDS = [("dental", "Dental clinic", "Smile Care Dental Studio"), ("skin", "Skin / Hair / Cosmetic clinic", "Glow Skin Clinic"),
         ("eye", "Eye clinic", "Clear Vision Eye Centre"), ("fertility_women", "Fertility / Women's clinic", "New Hope Women's Clinic"),
         ("ortho_physio", "Orthopaedic / Physiotherapy clinic", "Motion Physio & Ortho"), ("doctor", "Doctor's clinic", "Dr. Ghosh's Clinic")]
DEMO_DAY = date(2026, 11, 16)
TOTAL_13_NOV = [{"city": "TOTAL", "clinics": 61025, "phone": 59861, "email": 29538, "consult": 396}]
SHOTS = """
const { chromium } = require('playwright');
(async () => {
  const [dir, out] = process.argv.slice(2);
  const b = await chromium.launch();
  for (const ed of ['in', 'intl']) {
    const p = await b.newPage({ viewport: { width: 816, height: 1056 }, deviceScaleFactor: 1.25 });
    await p.goto('file://' + dir + '/b-' + ed + '.html');
    await p.evaluate(() => document.fonts.ready);
    const pages = await p.$$('section.page');
    for (let i = 0; i < pages.length; i++)
      await pages[i].screenshot({ path: out + '/brochure-' + ed + '-' + (i + 1) + '.jpg', type: 'jpeg', quality: 80 });
  }
  await b.close();
})();
"""


def clinic_mail() -> list[dict]:
    o = C._merge(C.load(ROOT / "config" / "outreach.toml"),
                 {"sender": {"name": "Your Name", "business": "Aurenflow", "phone": "+91 your number", "postal_address": ""}})
    out = []
    for key, label, name in KINDS:
        ld = Lead(key=f"demo-{key}", lead_id="CCU-1", business=name, category_key=key, category_label=label,
                  emails=["clinic@example.com"], market="in", country="IN", tz="Asia/Kolkata", city="Kolkata")
        subject, first = T.first_email(ld, o)
        out.append({"label": label, "business": name, "subject": subject, "first": first,
                    "f1": T.follow_up(ld, o, 1), "f2": T.follow_up(ld, o, 2), "reply": T.auto_reply(ld, o)})
    return out


def patients(tmp: Path) -> dict:
    out = {}
    for cc, tz in (("IN", "Asia/Kolkata"), ("US", "America/New_York")):
        c = Clinic(make_demo(tmp / cc.lower(), DEMO_DAY, cc))
        at = lambda hm: datetime.combine(DEMO_DAY, datetime.strptime(hm, "%H:%M").time(), ZoneInfo(tz)).timestamp()  # noqa: E731
        msgs = []
        for hm in ("09:30", "16:00"):
            for d in c.due(at(hm)):
                if not any(m["to"] == d.patient.name and m["kind"] == d.kind for m in msgs):
                    msgs.append({"kind": d.kind, "label": d.label, "to": d.patient.name, "email": d.patient.email,
                                 "time": hm, "subject": d.subject, "body": d.body})
        fmt = lambda x, f: x.strftime(f) if x else ""  # noqa: E731
        pts = [{"name": p.name, "consent": p.consent, "appointment": fmt(p.appointment, "%a %d %b, %H:%M"),
                "last_visit": fmt(p.last_visit, "%d %b"), "review_due": fmt(p.review_due, "%d %b"),
                "missed": fmt(p.missed, "%d %b")} for p in c.patients()]
        out[cc] = {"messages": msgs, "patients": pts, "sheet": c.sheet(at("08:00")), "name": c.cfg["name"]}
        c.close()
    return out


def lead_counts(folder: Path | None) -> list[dict]:
    if not folder:
        return TOTAL_13_NOV
    known = {r["slug"]: r for r in csv.DictReader(open(ROOT / "config" / "cities.csv", encoding="utf-8"))}
    exports = []
    for slug, city in known.items():
        for name in (f"leads-{slug}.csv", f"{slug}.csv"):
            if (folder / name).exists():
                exports.append((city, cm.read_csv(str(folder / name))))
                break
    return [{"city": r["City"], "clinics": r["Clinics"], "phone": r["With phone"], "email": r["With e-mail"],
             "consult": r["Hospital doctors with own clinic"]} for r in sl.summary(sl.build(exports))]


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit(__doc__)
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data = {"clinic_mail": clinic_mail(), "patients": patients(tmp)}
        leads = lead_counts(Path(argv[1]) if len(argv) > 1 else None)
        for ed, flag in (("in", []), ("intl", ["--edition", "intl"])):
            subprocess.run([sys.executable, str(ROOT / "marketing" / "build_brochure.py"), "--html", *flag,
                            "--out", str(tmp / f"b-{ed}.pdf")], check=True, capture_output=True)
        (tmp / "shots.js").write_text(SHOTS, encoding="utf-8")
        subprocess.run(["node", str(tmp / "shots.js"), str(tmp), str(out.resolve())], check=True)
    shutil.copy(ROOT / "marketing" / "brochure.pdf", out / "brochure-india.pdf")
    shutil.copy(ROOT / "marketing" / "brochure-intl.pdf", out / "brochure-international.pdf")
    js = lambda x: json.dumps(x, ensure_ascii=False, default=str).replace("</", "<\\/")  # noqa: E731
    page = (ROOT / "demo" / "hub-template.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(page.replace("__DATA__", js(data)).replace("__LEADS__", js(leads)), encoding="utf-8")
    print(f"wrote {out / 'index.html'} with {len(data['clinic_mail'])} clinic e-mail sets, "
          f"{sum(len(v['messages']) for v in data['patients'].values())} patient messages, {len(leads)} lead rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
