"""Small polite HTTP helper (standard library only)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "ClinicLeadsBot/0.1 (public business listings research)"


class FetchError(Exception):
    pass


def fetch(url: str, data: dict | None = None, timeout: int = 200,
          retries: int = 3, max_bytes: int = 60_000_000) -> bytes:
    """GET (or POST when data is given). Retries only on overload/timeout."""
    body = urllib.parse.urlencode(data).encode() if data else None
    last = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(max_bytes)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code not in (429, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
        if attempt < retries:
            time.sleep(min(60, 5 * 2 ** attempt))
    raise FetchError(f"{url.split('?')[0]} failed: {last}")


def fetch_json(url: str, data: dict | None = None, **kw) -> dict:
    raw = fetch(url, data, **kw)
    try:
        return json.loads(raw)
    except ValueError as e:
        raise FetchError(f"{url.split('?')[0]} returned non-JSON: {raw[:120]!r}") from e
