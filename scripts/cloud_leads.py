"""Lead pull for a place where the usual download does not work (a Claude cloud session).

The lead finder normally reads Overture Maps through DuckDB's web add-on, which a locked-down
network cannot install. This reads the same public files with plain range requests instead:
only each file's index and the sections that cover our cities (about 550 MB of 12 GB for the
27 cities), written into sparse local copies that DuckDB then reads as ordinary files.

    python scripts/cloud_leads.py fetch              # once: indexes + the sections for config/cities.csv
    python scripts/cloud_leads.py run kolkata ...    # plan, find and export a city -> data/leads-<city>.csv
    python scripts/cloud_leads.py run --all
    python -m clinicleads shortlist                  # then: data/clinic-leads.xlsx

Website reading is switched off here (a cloud session cannot reach clinic websites), so e-mails
are the ones the open data already holds. On the tablet use `python -m clinicleads find CITY`.
"""
from __future__ import annotations

import csv
import glob
import json
import math
import os
import re
import struct
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WORK = os.path.join(ROOT, "state", "overture")
BUCKET = "overturemaps-us-west-2"


def cities() -> list[dict]:
    with open(os.path.join(ROOT, "config", "cities.csv"), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch() -> None:
    import duckdb
    import requests

    from leadgen.providers.overture import latest_release

    os.makedirs(WORK, exist_ok=True)
    release, sess = latest_release(), requests.Session()
    listing = sess.get(f"https://{BUCKET}.s3.amazonaws.com/", timeout=60,
                       params={"list-type": "2", "prefix": f"release/{release}/theme=places/type=place/"}).text
    for key, size in re.findall(r"<Key>([^<]+\.parquet)</Key>.*?<Size>(\d+)</Size>", listing):
        size, path = int(size), os.path.join(WORK, re.search(r"part-\d+", key).group(0) + ".parquet")
        if os.path.exists(path):
            continue
        url = f"https://{BUCKET}.s3.amazonaws.com/{key}"
        tail = sess.get(url, headers={"Range": f"bytes={size - 8}-{size - 1}"}, timeout=60).content
        if tail[4:] != b"PAR1":
            sys.exit(f"{key}: not a Parquet file")
        start = size - 8 - struct.unpack("<I", tail[:4])[0]
        index = sess.get(url, headers={"Range": f"bytes={start}-{size - 1}"}, timeout=300).content
        with open(path + ".tmp", "wb") as f:            # a sparse file: only the index is really on disk
            f.truncate(size)
            f.write(b"PAR1")
            f.seek(start)
            f.write(index)
        os.rename(path + ".tmp", path)
        with open(path + ".url", "w") as f:
            f.write(url)
    con = duckdb.connect()
    con.execute(f"""CREATE TABLE rg AS SELECT file_name, row_group_id,
        min(CASE WHEN path_in_schema='bbox, xmin' THEN stats_min END)::DOUBLE x0, max(CASE WHEN path_in_schema='bbox, xmin' THEN stats_max END)::DOUBLE x1,
        min(CASE WHEN path_in_schema='bbox, ymin' THEN stats_min END)::DOUBLE y0, max(CASE WHEN path_in_schema='bbox, ymin' THEN stats_max END)::DOUBLE y1,
        min(coalesce(dictionary_page_offset, data_page_offset)) lo, max(coalesce(dictionary_page_offset, data_page_offset) + total_compressed_size) hi
        FROM parquet_metadata('{WORK}/part-*.parquet') GROUP BY 1, 2""")
    need = {}
    for c in cities():
        lat, lon, r = float(c["lat"]), float(c["lon"]), float(c["radius_km"]) * 1.05
        dy, dx = r / 111.0, r / (111.0 * math.cos(math.radians(lat)))
        for f, g, lo, hi in con.execute("SELECT file_name, row_group_id, lo, hi FROM rg WHERE x1>=? AND x0<=? AND y1>=? AND y0<=?",
                                        [lon - dx, lon + dx, lat - dy, lat + dy]).fetchall():
            need[(f, g)] = (lo, hi)
    done_file = os.path.join(WORK, "done.json")
    done = set(map(tuple, json.load(open(done_file)))) if os.path.exists(done_file) else set()
    todo = [(k, v) for k, v in need.items() if k not in done]
    print(f"release {release}: {len(need)} sections cover the cities, {len(todo)} to download "
          f"({sum(hi - lo for _, (lo, hi) in todo) / 1e6:.0f} MB)", flush=True)

    def get(item):
        (path, group), (lo, hi) = item
        url = open(path + ".url").read()
        for _ in range(3):
            try:
                r = sess.get(url, headers={"Range": f"bytes={lo}-{hi - 1}"}, timeout=180)
            except requests.RequestException:
                continue
            if r.status_code == 206 and len(r.content) == hi - lo:
                with open(path, "r+b") as f:
                    f.seek(lo)
                    f.write(r.content)
                return path, group
        return None

    with ThreadPoolExecutor(4) as pool:
        got = [x for x in pool.map(get, todo) if x]
    json.dump(sorted(done | set(got)), open(done_file, "w"))
    print(f"downloaded {len(got)}, failed {len(todo) - len(got)}" + ("" if len(got) == len(todo) else " - run fetch again"))


def run(slugs: list[str]) -> None:
    from leadgen.cli import main
    from leadgen.providers import overture

    if not glob.glob(os.path.join(WORK, "part-*.parquet")):
        sys.exit("Run first: python scripts/cloud_leads.py fetch")
    original = overture.fetch_area
    overture.fetch_area = lambda release, bbox, codes, min_conf, timeout_s=600, source=None: \
        original(release, bbox, codes, min_conf, timeout_s, source=os.path.join(WORK, "part-*.parquet"))
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    for slug in slugs:
        hits = glob.glob(os.path.join(ROOT, "config", "??", f"{slug}.toml"))
        if not hits:
            print(f"{slug}: not in config/cities.csv")
            continue
        base, cc = os.path.dirname(hits[0]), os.path.basename(os.path.dirname(hits[0]))
        cfg = os.path.join(WORK, f"{slug}.toml")
        with open(cfg, "w") as f:                       # the city's settings, minus everything that needs open internet
            f.write(f'include = ["{ROOT}/config/shared/categories.toml", "{base}/_base.toml", "{hits[0]}"]\n'
                    "[plan]\ndays = 1\n[enrich]\nwebsite = false\nemail_hunt = false\nemail_archive = false\n"
                    "check_email_mx = false\napi_enrich = false\n[sheets]\nenabled = false\n[runtime]\ntime_budget_minutes = 40\n")
        db = os.path.join(ROOT, "state", f"{cc}-{slug}.sqlite")
        out = os.path.join(ROOT, "data", f"leads-{slug}.csv")
        for argv in (["plan", "--config", cfg, "--db", db, "--offline"], ["run", "--config", cfg, "--db", db, "--no-sheets"],
                     ["export-csv", "--config", cfg, "--db", db, "--out", out]):
            try:
                code = main(argv)
            except SystemExit as e:
                code = e.code
            if code:
                print(f"{slug}: {argv[0]} failed")
                break
        else:
            with open(out, newline="", encoding="utf-8") as f:
                print(f"{slug}: {sum(1 for _ in csv.reader(f)) - 1} leads -> {out}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
        fetch()
    elif len(sys.argv) >= 3 and sys.argv[1] == "run":
        run([c["slug"] for c in cities()] if sys.argv[2] == "--all" else sys.argv[2:])
    else:
        sys.exit(__doc__)
