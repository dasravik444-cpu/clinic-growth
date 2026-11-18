"""Research doctors from what their own websites publish, for the columns map data cannot fill: degrees, the year
they qualified, years of experience, the hospitals they work at, a registration number, and the WhatsApp and
e-mail the site gives. On the tablet:  cg research  (reads the doctor tables from the Download folder).

Nothing is guessed. Degrees, years, age and registration numbers are kept only when they stand next to the
doctor's name on the page; experience and hospitals only next to the name or on a page titled with it. Every fact
keeps the page it came from. A cell already filled (by a web search or an earlier run) is never overwritten. The
crawler names itself (ClinicGrowthBot) and obeys robots.txt.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from . import profile as P
from .model import person_tokens

BOT_NAME = "ClinicGrowthBot"
BOT_UA = f"Mozilla/5.0 (compatible; {BOT_NAME}/2.0; +https://github.com/dasravik444-cpu/clinic-growth)"
MAX_PAGES = 5
DONE_MARK = "Own website read"           # in Research notes: this row's website has been researched
REFUSED = "the website asks robots not to read it"
PAGE_WORDS = re.compile(r"about|doctor|dr[-_.]|profile|meet|team|bio|qualif|experience|consultant|chamber|contact",
                        re.I)
SKIP_LINK = re.compile(r"\.(?:jpe?g|png|gif|webp|svg|pdf|zip|mp4|mp3|docx?|xlsx?)(?:$|\?)|/wp-(?:admin|login)|"
                       r"/(?:cart|checkout|feed|tag|category)/|mailto:|tel:|javascript:", re.I)
CORE = {"MBBS", "BDS", "BPT", "BAMS", "BHMS", "BUMS"}
DEGREE = re.compile(P.DEGREES.pattern + r"(?:\s*[(\[]\s*([A-Za-z&.,' -]{3,45}?)\s*[)\]])?")
YEAR = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
EXPERIENCE = [
    re.compile(r"(?:over|more than|nearly|about|around|almost)?\s*\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\.?\s+(?:of\s+)?"
               r"(?:[A-Za-z]+\s+){0,3}?experience", re.I),
    re.compile(r"experience\s*(?:of|:|-)?\s*(?:over|more than|nearly|about|around|almost)?\s*\b(\d{1,2})\s*\+?\s*"
               r"(?:years?|yrs?)", re.I),
]
HOSPITAL = re.compile(r"\b((?:[A-Z][A-Za-z.&'’-]*[ \t]+){1,6}(?:Hospitals?|Medical College(?:[ \t]+(?:and|&)[ \t]+"
                      r"Hospital)?|Nursing Home|Medical Cent(?:re|er)|Institute of(?:[ \t]+[A-Z][A-Za-z&-]*){1,4}))")
HOSPITAL_STOP = {"the", "our", "best", "top", "a", "any", "your", "this", "at", "in", "of", "and", "visit", "leading",
                 "private", "government", "multispeciality", "multispecialty", "multi", "super", "speciality",
                 "specialty", "reputed", "renowned", "famous", "various", "many", "other", "several", "all", "major",
                 "big", "well", "known", "consultant", "senior", "junior", "attached", "to", "with", "from", "worked",
                 "working", "currently", "presently", "formerly", "ex", "prestigious", "premier", "number", "one"}
EDUCATION = re.compile(r"\b(?:from|completed|graduat\w*|studied|passed|alumn\w*|degree|trained|training|MBBS|BDS|"
                       r"MD|MS|MDS|DNB|fellowship)\b", re.I)
REGISTRATION = re.compile(r"\b(?:Reg(?:istration|d|n)?\.?)[ \t]*(?:No|Number|#)\.?[ \t]*[:\-–.]?[ \t]*"
                          r"([A-Z]{0,6}[/ -]?\d{3,7}(?:[/-]\d{1,4})?[A-Z]?)\b", re.I)
COUNCIL = re.compile(r"council|medical|dental|wbmc|nmc|\bmci\b|\bdci\b", re.I)
# Age only from a labelled field ("Age: 45") or a stated year of birth, never from "patients above age 60".
AGE = [re.compile(r"\bAge\s*[:\-–]\s*(\d{2})\b"),
       re.compile(r"\b(?:born (?:in|on)|DOB|date of birth)\b[^.\n]{0,25}?\b(19[3-9]\d)\b", re.I)]
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "icloud.com",
             "live.com", "aol.com", "proton.me", "protonmail.com", "zoho.com"}
FACTS = ["Degrees (researched)", "Qualified (year, as published)", "Approx. age", "Experience (as published)",
         "Hospitals (researched)", "Registration no. (as published)"]


# ------------------------------------------------------------------------------------------------ reading pages
def name_words(doctor: str) -> list[str]:
    return [t for t in person_tokens(doctor) if len(t) >= 3]


def windows(lines: list[str], doctor: str) -> list[str]:
    """The text that follows each mention of the doctor's name, up to the next doctor ("Dr ...") or 400 characters."""
    words = name_words(doctor)
    if not words:
        return []
    text = "\n".join(lines)
    names = "|".join(re.escape(w) for w in words)
    name = re.compile(rf"\b(?:{names})\b", re.I)
    other = re.compile(rf"\b(?:dr|prof)\b\.?\s*(?!(?:{names})\b)[a-z]", re.I)   # the next doctor's name
    out = []
    for m in name.finditer(text):
        tail = text[m.end(): m.end() + 400]
        cut = other.search(tail)
        out.append(text[m.start(): m.end()] + (tail[: cut.start()] if cut else tail))
    return out


def degrees_in(parts: list[str]) -> tuple[str, str]:
    """(degrees, years qualified) named next to the doctor, e.g. ('MBBS, MS (Ophthalmology)', 'MBBS 2004')."""
    found, years = [], []
    for part in parts:
        ms = list(DEGREE.finditer(part))
        for i, m in enumerate(ms):
            deg = m.group(1).replace(".", "")
            if m.group(2):
                label = f"{deg} ({m.group(2).strip()})"
                if deg in found:
                    found[found.index(deg)] = label
                elif label not in found:
                    found.append(label)
            elif deg not in found and not any(f.startswith(deg + " (") for f in found):
                found.append(deg)
            after = part[m.end(): ms[i + 1].start() if i + 1 < len(ms) else m.end() + 90][:90]
            y = YEAR.search(after)
            if y and f"{deg} {y.group(1)}" not in years:
                years.append(f"{deg} {y.group(1)}")
    if not CORE & {f.split(" ")[0] for f in found}:      # "MS" or "DO" alone is too often something else
        return "", ""
    return ", ".join(found[:8]), ", ".join(years[:4])


def experience_in(parts: list[str]) -> str:
    for part in parts:
        for rx in EXPERIENCE:
            m = rx.search(part)
            if m and 1 <= int(m.group(1)) <= 60:
                return re.sub(r"\s+", " ", m.group(0)).strip()[:60]
    return ""


def hospitals_in(parts: list[str]) -> list[str]:
    out = []
    for part in parts:
        for line in part.split("\n"):
            for m in HOSPITAL.finditer(line):
                if EDUCATION.search(line[max(0, m.start() - 50): m.start()]):
                    continue                     # "MBBS from X Medical College": where they studied
                words = m.group(1).split()
                while words and words[0].lower().strip(".,") in HOSPITAL_STOP:
                    words = words[1:]
                if len(words) < 2:
                    continue
                name = " ".join(words)
                if name.lower() not in {x.lower() for x in out}:
                    out.append(name)
    return out[:6]


def registration_in(parts: list[str]) -> str:
    for part in parts:
        for line in part.split("\n"):
            m = REGISTRATION.search(line)
            if m and COUNCIL.search(line + " " + part[:200]):
                return re.sub(r"\s+", " ", m.group(0)).strip()[:60]
    return ""


def age_in(parts: list[str]) -> str:
    for part in parts:
        m = AGE[0].search(part)
        if m and 25 <= int(m.group(1)) <= 90:
            return f"{m.group(1)} (as published)"
        m = AGE[1].search(part)
        if m:
            return f"born {m.group(1)} (as published)"
    return ""


def page_text(html: str) -> tuple[str, list[str], list[tuple[str, str]]]:
    """(title, text lines, links) of a page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    links = [(a.get("href") or "", a.get_text(" ", strip=True)) for a in soup.find_all("a")]
    title = re.sub(r"\s+", " ", soup.title.get_text(" ") if soup.title else "").strip()
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    lines = [re.sub(r"\s+", " ", x).strip() for x in soup.get_text("\n").split("\n")]
    return title, [x for x in lines if x], links


def facts_from_pages(pages: list[tuple[str, str]], doctor: str) -> dict:
    """pages: (url, html). Returns {column: value}, plus '_sources' {column: url} and '_named' (the site names the
    doctor) and '_contacts' {WhatsApp/E-mail: (value, url)}."""
    from leadgen.enrich.emails import suspicious_email
    from leadgen.enrich.extract import extract_page

    out: dict = {"_sources": {}, "_named": False, "_contacts": {}}
    words = name_words(doctor)
    site = (urlsplit(pages[0][0]).hostname or "").lower().removeprefix("www.") if pages else ""
    degrees, years = [], []
    for url, html in pages:
        title, lines, _ = page_text(html)
        near = windows(lines, doctor)
        out["_named"] = out["_named"] or bool(near)
        titled = bool(words) and any(re.search(rf"\b{re.escape(w)}\b", title, re.I) for w in words)
        wide = near + (["\n".join(lines)] if titled else [])
        d, y = degrees_in(near)
        for label, src in ((d, degrees), (y, years)):
            for item in filter(None, label.split(", ")):
                if item not in src:
                    src.append(item)
                    out["_sources"].setdefault("Degrees (researched)" if src is degrees
                                               else "Qualified (year, as published)", url)
        for col, value in (("Experience (as published)", experience_in(wide)),
                           ("Hospitals (researched)", "; ".join(hospitals_in(wide))),
                           ("Registration no. (as published)", registration_in(near)),
                           ("Approx. age", age_in(near))):
            if value and col not in out:
                out[col] = value
                out["_sources"][col] = url
        pe = extract_page(html, url)
        for f in pe.found:
            if f.kind == "whatsapp" and f.how == "wa-link" and "WhatsApp" not in out["_contacts"]:
                out["_contacts"]["WhatsApp"] = (f.value, url)
            # the clinic's own address, or a personal mailbox; not the web designer's
            dom = f.value.rpartition("@")[2]
            own = dom in FREE_MAIL or site.endswith(dom) or dom.endswith(site)
            if f.kind == "email" and own and not suspicious_email(f.value) and "E-mail" not in out["_contacts"]:
                out["_contacts"]["E-mail"] = (f.value, url)
    if degrees:
        out["Degrees (researched)"] = ", ".join(degrees[:8])
    if years:
        out["Qualified (year, as published)"] = ", ".join(years[:4])
    return out


# ------------------------------------------------------------------------------------------------ the website
def site_url(url: str) -> str:
    url = (url or "").strip().split()[0] if (url or "").strip() else ""
    if url and "//" not in url:
        url = "http://" + url
    return url


def read_site(http, url: str) -> tuple[list[tuple[str, str]], str]:
    """The home page and up to MAX_PAGES-1 of its about/doctor/profile pages: ([(url, html)], note)."""
    from leadgen.net import BreakerOpen, FetchError, NetworkDown

    url = site_url(url)
    if not url:
        return [], "no website"
    try:
        allowed, _ = http.robots_allowed(url)
    except NetworkDown:
        raise
    except Exception:  # noqa: BLE001 - an odd site must not stop the run
        allowed = False
    if not allowed:
        why = http.robots_reason(url) if hasattr(http, "robots_reason") else ""
        if why in ("", "disallowed"):
            return [], REFUSED
        code = re.search(r"HTTP (\d+)", why)
        return [], f"the website answered HTTP {code.group(1)}" if code else "the website did not answer"
    queue, seen, pages, note = [url], set(), [], ""
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    while queue and len(pages) < MAX_PAGES:
        u = queue.pop(0)
        if u in seen:
            continue
        seen.add(u)
        try:
            if not http.robots_allowed(u)[0]:
                continue
            r = http.get(u, timeout=20, max_bytes=2_000_000, retries=1, browser=True)
        except NetworkDown:
            raise
        except (FetchError, BreakerOpen) as exc:
            if not pages:
                note = "the website did not answer" + (" in time" if "timed out" in str(exc).lower() else "")
            continue
        if r.status >= 400 or "html" not in (r.content_type or "text/html"):
            if not pages:
                note = f"the website answered HTTP {r.status}"
            continue
        pages.append((r.url or u, r.text))
        if len(pages) == 1:
            _, _, links = page_text(r.text)
            cands = []
            for href, text in links:
                full = urlunsplit(urlsplit(urljoin(r.url or u, href))._replace(fragment=""))
                h = (urlsplit(full).hostname or "").lower().removeprefix("www.")
                if h == host and not SKIP_LINK.search(full) and PAGE_WORDS.search(href + " " + text):
                    if full not in cands and full.rstrip("/") != (r.url or u).rstrip("/"):
                        cands.append(full)
            # about/doctor/profile pages before contact pages
            cands.sort(key=lambda x: "contact" in x.lower())
            queue += cands[: MAX_PAGES - 1]
    return pages, ("" if pages else note or "the website did not answer")


def research(http, url: str, doctor: str) -> dict:
    """Everything the doctor's own website publishes for the researched columns, with sources and a note."""
    pages, note = read_site(http, url)
    if not pages:
        # a site that refuses robots is final; one that did not answer is tried again on the next run (once)
        return {"_note": f"Website not read: {note}.", "_sources": {}, "_contacts": {}, "_retry": note != REFUSED}
    found = facts_from_pages(pages, doctor)
    facts = [c for c in FACTS if found.get(c)]
    if not found["_named"]:
        note = f"{DONE_MARK} ({len(pages)} pages): it does not name {doctor}, so nothing was taken about the doctor."
        found = {"_sources": {}, "_contacts": found["_contacts"]}
    elif facts:
        note = f"{DONE_MARK} ({len(pages)} pages)."
    else:
        note = f"{DONE_MARK} ({len(pages)} pages): it names the doctor but publishes none of these details."
    found["_note"] = note
    return found


# ------------------------------------------------------------------------------------------------ the table
def merge(row: dict, found: dict, when: str, how: str = "website") -> bool:
    """Fill the row's empty researched cells from found; never overwrite. True when a cell was filled."""
    filled = False
    sources = (row.get("Research sources") or "").split()
    for col in FACTS + ["Research: same doctor?"]:
        if found.get(col) and not str(row.get(col) or "").strip():
            row[col] = found[col]
            filled = True
            src = found.get("_sources", {}).get(col)
            if src and src not in sources:
                sources.append(src)
    if how == "website" and any(found.get(c) for c in FACTS) and not str(row.get("Research: same doctor?") or "").strip():
        row["Research: same doctor?"] = "Sure: the doctor's own website (the lead's site) names them"
    for col, (value, src) in found.get("_contacts", {}).items():
        if not str(row.get(col) or "").strip():
            row[col] = value
            filled = True
            if src not in sources:
                sources.append(src)
    for src in found.get("_extra_sources", []):
        if src not in sources:
            sources.append(src)
    row["Research sources"] = " ".join(sources)
    note = found.get("_note", "")
    old = str(row.get("Research notes") or "").strip()
    if note and note not in old:
        row["Research notes"] = f"{old} {note}".strip()
    stamp = f"{when} {how}"
    old = str(row.get("Researched on") or "").strip()
    if stamp not in old:
        row["Researched on"] = f"{old}; {stamp}".strip("; ")
    return filled


def apply_known(rows: list[dict], known: dict, when: str, how: str = "web search") -> int:
    """Web-search findings by Lead ID ({lead_id: {column: value}}, 'Research sources' space-separated) into rows."""
    n = 0
    for r in rows:
        k = known.get(str(r.get("Lead ID") or ""))
        if not k:
            continue
        found = {c: v for c, v in k.items() if c in FACTS or c == "Research: same doctor?"}
        found["_extra_sources"] = (k.get("Research sources") or "").split()
        found["_note"] = k.get("Research notes", "")
        merge(r, found, when, how)
        n += 1
    return n


def read_table(path) -> tuple[str, list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(str(path), read_only=True)
    title = ""
    if "Read me" in wb.sheetnames:
        title = next(wb["Read me"].iter_rows(max_row=1, values_only=True), [""])[0] or ""
    rows = list(wb["Clinics"].iter_rows(values_only=True))
    if not rows:
        return title, []
    head = [str(h or "") for h in rows[0]]
    out = [{h: ("" if v is None else v) for h, v in zip(head, r)} for r in rows[1:]]
    wb.close()
    return title, out


def todo(rows: list[dict]) -> list[dict]:
    """Rows with a doctor and an own website whose website has not been read yet."""
    return [r for r in rows if str(r.get("Website") or "").strip() and str(r.get("Doctor") or "").strip()
            and DONE_MARK not in str(r.get("Research notes") or "")
            and REFUSED not in str(r.get("Research notes") or "")]


def needs_read(hit: dict | None) -> bool:
    return hit is None or (bool(hit.get("_retry")) and hit.get("_tries", 1) < 2)


def run_files(paths: list, http=None, *, limit: int = 300, workers: int = 4, cache_path=None, out_dir=None,
              today: str | None = None, say=print) -> dict:
    """Research the doctors in these tables (newest first: an earlier '-researched' copy is continued). Writes
    NAME-researched.xlsx next to each file (or into out_dir). Sites already read (cache) are not read again."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    today = today or dt.date.today().isoformat()
    if http is None:
        from leadgen.net import Http

        http = Http(user_agent=BOT_UA, robot_name=BOT_NAME, default_interval=2.0)
    cache_path = Path(cache_path) if cache_path else None
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
    stats = {"sites read": 0, "rows filled": 0, "files": []}
    budget = limit
    for path in paths:
        path = Path(path)
        if path.stem.endswith("-researched"):
            continue
        out = Path(out_dir or path.parent) / f"{path.stem}-researched.xlsx"
        title, rows = read_table(out if out.exists() else path)
        work = todo(rows)
        fresh = [r for r in work if needs_read(cache.get(site_url(r["Website"])))][:max(0, budget)]
        budget -= len(fresh)
        say(f"{path.name}: {len(work)} doctor{'' if len(work) == 1 else 's'} with a website still to research, "
            f"reading {len(fresh)} now...")
        sites = {}
        for r in fresh:
            sites.setdefault(site_url(r["Website"]), str(r["Doctor"]))
        done = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            jobs = {pool.submit(research, http, url, doc): url for url, doc in sites.items()}
            for job in as_completed(jobs):
                url = jobs[job]
                tries = (cache.get(url) or {}).get("_tries", 0) + 1
                try:
                    cache[url] = {**job.result(), "_tries": tries}
                except Exception as exc:  # noqa: BLE001 - one bad site must not stop the rest
                    if type(exc).__name__ == "NetworkDown":
                        say("The internet connection dropped: stopping here, the next run continues.")
                        break
                    cache[url] = {"_note": f"Website not read: {type(exc).__name__}.", "_sources": {}, "_contacts": {},
                                  "_retry": True, "_tries": tries}
                done += 1
                stats["sites read"] += 1
                if done % 10 == 0:
                    say(f"  {done} of {len(sites)} websites read")
                    if cache_path:
                        cache_path.write_text(json.dumps(cache), encoding="utf-8")
        for r in work:
            hit = cache.get(site_url(r["Website"]))
            if not hit or needs_read(hit) or (hit.get("_note") and hit["_note"] in str(r.get("Research notes") or "")):
                continue                         # not read yet, or already written into this row
            if merge(r, hit, today):
                stats["rows filled"] += 1
        title = title or path.stem
        P.write_xlsx(rows, str(out), title)
        stats["files"].append(str(out))
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return stats
