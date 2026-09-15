# hud user api: fair market rents and income limits by metro area. every
# metro entity and year is one call, so the run covers the study years plus
# the newest year each dataset offers rather than every year since 2014
import json
import math
import re
import time

import pandas as pd
import requests

from bot.common import INTEGRATED, RAW_DIR, STUDY_YEARS, USER_AGENT, env_key, manifest_entry, write_manifest

OUT_DIR = RAW_DIR / "hud"
OUT_FILE = OUT_DIR / "metrics.csv"
API = "https://www.huduser.gov/hudapi/public"
LIST_URL = f"{API}/fmr/listMetroAreas"
FMR_URL = f"{API}/fmr/data/"
IL_URL = f"{API}/il/data/"
PROVIDER = "U.S. Department of Housing and Urban Development, HUD User"
COLUMNS = ["cbsa_code", "metric", "period", "value"]
TWO_BEDROOM = "Two-Bedroom"

# same timeout as bot.common.fetch, and never more than two requests a second
TIMEOUT = 120
MIN_INTERVAL = 0.5

# a metro entity id carries the cbsa code twice, METRO10180M10180. a hud metro
# fmr subarea carries MM plus an old pmsa code or N plus a county fips instead,
# as in METRO29180N22001, and covers only part of the metro
ENTITY = re.compile(r"^METRO(\d{5})M(\d{5})$")


# the list endpoints wrap their rows in "data". a bare list is accepted too
def list_entries(payload):
    if isinstance(payload, dict):
        payload = payload.get("data")
    return payload if isinstance(payload, list) else []


# cbsa code -> whole metro entity id. subareas, malformed rows and repeats
# are dropped, and the first entity seen for a code wins
def parse_metro_list(payload):
    ids = {}
    for entry in list_entries(payload):
        if not isinstance(entry, dict):
            continue
        match = ENTITY.match(str(entry.get("cbsa_code", "")).strip())
        if match and match.group(1) == match.group(2):
            ids.setdefault(match.group(1), match.group(0))
    return ids


# hud flags the metro's own row inside a zip breakdown as "MSA level"
def _is_metro_level(entry):
    return isinstance(entry, dict) and any(
        re.sub(r"[^a-z]", "", value.lower()) == "msalevel"
        for value in entry.values() if isinstance(value, str)
    )


# a plain area answers with one object, a small area fmr metro with a list of
# zip rows where the metro's own row is flagged. none when no metro row exists
def metro_record(block):
    if isinstance(block, dict):
        return block
    if isinstance(block, list):
        return next((entry for entry in block if _is_metro_level(entry)), None)
    return None


# hud sends "948.0" in some years and 948 in others. a rent or an income is
# positive, so zero and below count as missing
def to_number(value):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _data(payload):
    return metro_record(payload.get("data")) if isinstance(payload, dict) else None


# two bedroom fair market rent of the metro, dollars a month
def parse_fmr(payload):
    data = _data(payload)
    basic = metro_record(data.get("basicdata")) if data else None
    return to_number(basic.get(TWO_BEDROOM)) if basic else None


# median family income behind the income limits, dollars a year
def parse_income_limits(payload):
    data = _data(payload)
    return to_number(data.get("median_income")) if data else None


# the year a payload describes. fmr keeps it inside basicdata in some years
def payload_year(payload):
    data = _data(payload)
    if not data:
        return None
    year = data.get("year")
    if year is None and isinstance(data.get("basicdata"), dict):
        year = data["basicdata"].get("year")
    text = str(year).strip() if year is not None else ""
    return int(text) if text.isdigit() else None


# one row per code, metric and year in the map's four columns. missing values
# are dropped and a repeat of the same key keeps the last value seen
def build_rows(records):
    rows = [(code, metric, str(year), value) for code, metric, year, value in records if value is not None]
    df = pd.DataFrame(rows, columns=COLUMNS)
    df = df.drop_duplicates(["cbsa_code", "metric", "period"], keep="last")
    return df.sort_values(["metric", "cbsa_code", "period"]).reset_index(drop=True)


# study code -> geo level, sorted by code
def study_codes(path):
    df = pd.read_csv(path, dtype=str, usecols=["cbsa_code", "geo_level"]).drop_duplicates("cbsa_code")
    return dict(sorted(zip(df["cbsa_code"].str.strip(), df["geo_level"].fillna("msa"))))


DATASETS = {
    "fmr": (FMR_URL, "fmr_2br", parse_fmr),
    "il": (IL_URL, "median_family_income", parse_income_limits),
}


# bot.common.fetch cannot send a header, so this repeats its policy for the
# bearer token: same user agent and timeout, retries on connection errors and
# 5xx, plus 429, and a pause that keeps requests at two a second. the token
# lives only in the header and is stripped from any error text
class Client:
    def __init__(self, token):
        self.token = token
        self.headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"}
        self.last = 0.0

    def pace(self):
        wait = MIN_INTERVAL - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()

    def get(self, url, params=None, retries=3):
        last_error = None
        for attempt in range(retries):
            self.pace()
            try:
                response = requests.get(url, params=params, timeout=TIMEOUT, headers=self.headers)
                if response.status_code < 500 and response.status_code != 429:
                    return response
                last_error = RuntimeError(f"HTTP {response.status_code}")
            except requests.RequestException as e:
                last_error = RuntimeError(str(e).replace(self.token, "<token>"))
            time.sleep(2 ** attempt)
        raise last_error

    # (status, body). 401 and 403 stop the run. anything else that is not a
    # 200 with valid json comes back with no body for the caller to count
    def get_json(self, url, params=None):
        response = self.get(url, params=params)
        status = response.status_code
        if status in (401, 403):
            raise RuntimeError(f"hud returned HTTP {status}, check HUD_API_TOKEN and its dataset registration")
        if status != 200:
            return status, None
        try:
            return status, response.json()
        except ValueError:
            return "malformed", None


# the year hud answers with when none is asked for. tries a few entities in
# case the first has no current row
def newest_year(client, base, entities):
    for entity in list(entities)[:3]:
        _, payload = client.get_json(base + entity)
        year = payload_year(payload)
        if year:
            return year
    return None


def collect():
    token = env_key("HUD_API_TOKEN")
    if not token:
        print("[hud] HUD_API_TOKEN is not set, source skipped")
        return None
    client = Client(token)

    print("[hud] fetching the metro area list")
    status, listing = client.get_json(LIST_URL)
    ids = parse_metro_list(listing)
    if not ids:
        raise RuntimeError(f"hud metro list came back empty (HTTP {status})")

    # divisions never match, hud keys on the cbsa code, so the build gives
    # each one its parent metro's values
    levels = study_codes(INTEGRATED)
    entities = {code: ids[code] for code in levels if code in ids}
    absent = [code for code in levels if code not in ids]
    divisions = sum(levels[code] == "division" for code in absent)
    print(f"[hud] {len(entities)} of {len(levels)} study codes have a metro entity, "
          f"{len(absent) - divisions} metros and {divisions} divisions without one, "
          f"{len(list_entries(listing)) - len(ids)} subarea or repeated entries skipped")
    if not entities:
        raise RuntimeError("no study code matches a hud metro entity")

    newest, years_for = {}, {}
    for dataset, (base, _, _) in DATASETS.items():
        newest[dataset] = newest_year(client, base, entities.values())
        years_for[dataset] = sorted(set(STUDY_YEARS) | ({newest[dataset]} if newest[dataset] else set()))
    print(f"[hud] newest years: fmr {newest['fmr']}, il {newest['il']}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records, skipped, raw_files = [], {}, []
    for year in sorted(set(years_for["fmr"]) | set(years_for["il"])):
        captured = {"year": year, "fmr": {}, "il": {}}
        for dataset, (base, metric, parse) in DATASETS.items():
            if year not in years_for[dataset]:
                continue
            found = 0
            for code, entity in entities.items():
                status, payload = client.get_json(base + entity, {"year": year})
                if not isinstance(payload, dict) or "data" not in payload:
                    key = str(status) if payload is None else "nodata"
                    skipped[key] = skipped.get(key, 0) + 1
                    continue
                captured[dataset][entity] = payload
                value = parse(payload)
                if value is not None:
                    records.append((code, metric, year, value))
                    found += 1
            print(f"[hud] {dataset} {year}: {found} of {len(entities)} metros with a value")
        count = len(captured["fmr"]) + len(captured["il"])
        if count:
            path = OUT_DIR / f"hud_{year}.json"
            path.write_text(json.dumps(captured) + "\n")
            raw_files.append((path, year, count))

    df = build_rows(records)
    df.to_csv(OUT_FILE, index=False)

    all_years = sorted(set(years_for["fmr"]) | set(years_for["il"]))
    have = set(df["period"])
    through = {}
    for dataset, (_, metric, _) in DATASETS.items():
        periods = df.loc[df["metric"] == metric, "period"]
        through[dataset] = periods.max() if len(periods) else "none"
    entries = [manifest_entry(
        OUT_FILE, FMR_URL + "{entityid}?year={year}", PROVIDER,
        "Fair market rents, two bedroom, and income limits, median family income, by metro area and fiscal year",
        f"fmr through {through['fmr']}, income limits through {through['il']}", len(df),
        {
            "income_limits_endpoint": IL_URL + "{entityid}?year={year}",
            "metro_list": LIST_URL,
            "entities": len(entities),
            "study_codes": len(levels),
            "years": years_for,
            "years_without_data": [y for y in all_years if str(y) not in have],
            "responses_skipped": skipped,
        },
    )]
    for path, year, count in raw_files:
        entries.append(manifest_entry(
            path, API, PROVIDER, f"raw fmr and il responses per metro entity for fiscal year {year}",
            str(year), count,
        ))
    write_manifest(OUT_DIR, entries)
    print(f"[hud] {len(df)} rows, {df['metric'].nunique()} metrics -> {OUT_FILE.name}")
    return OUT_FILE
