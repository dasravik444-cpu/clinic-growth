"""Read a clinic's own website for the contact routes it publishes.

Fetches the homepage and at most two contact/about pages, only where robots.txt
allows. Nothing is guessed: every value was literally on the page.
"""
from __future__ import annotations

import html
import re
import time
import urllib.parse
import urllib.robotparser

from .model import Lead
from .net import USER_AGENT, FetchError, fetch

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
HREF = re.compile(r'href\s*=\s*["\']([^"\'#]+)["\']', re.I)
WA = re.compile(r"https?://(?:wa\.me/|api\.whatsapp\.com/send\?phone=)\+?(\d{8,15})", re.I)
JUNK = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "sentry", "wixpress",
        "example.", "@2x", "yourname", "domain.com")
CONTACT_HINT = re.compile(r"contact|about|appointment|reach|location", re.I)


def extract(page: str) -> dict:
    text = html.unescape(page)
    emails = []
    for e in EMAIL.findall(text):
        e = e.strip(".").lower()
        if not any(j in e for j in JUNK) and e not in emails:
            emails.append(e)
    phones = []
    for h in HREF.findall(text):
        if h.lower().startswith("tel:"):
            p = urllib.parse.unquote(h[4:]).strip()
            if p and p not in phones:
                phones.append(p)
    wa = WA.findall(text)
    return {"emails": emails, "phones": phones, "whatsapp": wa[0] if wa else ""}


def contact_links(page: str, base: str, limit: int = 2) -> list[str]:
    host = urllib.parse.urlparse(base).netloc
    out = []
    for h in HREF.findall(page):
        if h.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urllib.parse.urljoin(base, h)
        if urllib.parse.urlparse(url).netloc == host and CONTACT_HINT.search(h) and url not in out:
            out.append(url)
        if len(out) >= limit:
            break
    return out


def _allowed(url: str) -> bool:
    parts = urllib.parse.urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    try:
        raw = fetch(f"{parts.scheme}://{parts.netloc}/robots.txt", timeout=20, retries=0,
                    max_bytes=500_000)
        rp.parse(raw.decode("utf-8", "replace").splitlines())
    except FetchError as e:
        return "HTTP 404" in str(e)      # no robots file = allowed; any other failure = skip
    return rp.can_fetch(USER_AGENT, url)


def enrich(lead: Lead, pause: float = 2.0, fetcher=fetch, allowed=_allowed) -> bool:
    """Fill empty email / phone / whatsapp from the lead's own site. True if changed."""
    url = lead.website.strip()
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if not allowed(url):
        return False
    found = {"emails": [], "phones": [], "whatsapp": ""}
    try:
        home = fetcher(url, timeout=30, retries=0, max_bytes=2_000_000).decode("utf-8", "replace")
    except FetchError:
        return False
    pages = [home]
    for link in contact_links(home, url):
        time.sleep(pause)
        try:
            if allowed(link):
                pages.append(fetcher(link, timeout=30, retries=0,
                                     max_bytes=2_000_000).decode("utf-8", "replace"))
        except FetchError:
            continue
    for p in pages:
        got = extract(p)
        found["emails"] += [e for e in got["emails"] if e not in found["emails"]]
        found["phones"] += [x for x in got["phones"] if x not in found["phones"]]
        found["whatsapp"] = found["whatsapp"] or got["whatsapp"]
    changed = False
    if not lead.email and found["emails"]:
        lead.email, changed = found["emails"][0], True
    if not lead.phone and found["phones"]:
        lead.phone, changed = found["phones"][0], True
    if not lead.whatsapp and found["whatsapp"]:
        lead.whatsapp, changed = found["whatsapp"], True
    return changed
