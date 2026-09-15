import copy
import json
import math
import re
import time

import pandas as pd

from bot.common import RAW_DIR, env_key, fetch, manifest_entry, write_manifest

OUT_DIR = RAW_DIR / "bea"
ENDPOINT = "https://apps.bea.gov/api/data"
PROVIDER = "U.S. Bureau of Economic Analysis"
DATASET = "Regional"
TABLE = "CAINC1"
FIRST_YEAR = 2014
# bea asks for no more than one request a second
PAUSE_SECONDS = 1.0

# cainc1 line codes and the metric each one feeds. line 2 is population, which
# the census vintages already cover. phrase is what the line's description
# must say, unit_mult the power of ten bea reports the value in
LINES = {
    "1": {"metric": "bea_personal_income", "phrase": "personal income", "unit_mult": 3},
    "3": {"metric": "bea_income_per_capita", "phrase": "per capita personal income", "unit_mult": 0},
}
COLUMNS = ["cbsa_code", "metric", "period", "value"]

# the msa pull also carries the national metro and nonmetro portions
NATIONAL = {"00000", "00998", "00999"}
FIPS = re.compile(r"\d{5}")
YEAR = re.compile(r"\d{4}")
TAG = re.compile(r"\[(\w+)\]")


# the key must never reach a message, a file or the manifest
def redact(text, key):
    text = str(text)
    if not key:
        return text
    return re.sub(re.escape(key), "REDACTED", text, flags=re.IGNORECASE)


# "10180", "10180 " or "10180M" -> "10180", leading zeros kept. national
# portions and anything not starting with five digits yield none
def cbsa_code(geo_fips):
    match = FIPS.match(str(geo_fips or "").strip())
    if not match or match.group(0) in NATIONAL:
        return None
    return match.group(0)


# a four digit calendar year as an int, none for anything else
def period_year(text):
    text = str(text or "").strip()
    return int(text) if YEAR.fullmatch(text) else None


# "7,116,829" -> 7116829.0. bea flags a missing value in parentheses, (NA) or (D)
def parse_value(text):
    if text is None:
        return None
    cleaned = str(text).replace(",", "").strip()
    if not cleaned or cleaned.startswith("("):
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


# the results block of a response. bea reports failures inside a 200, either
# at the top level or inside results, so both become an exception here
def results(payload):
    api = payload.get("BEAAPI") if isinstance(payload, dict) else None
    if not isinstance(api, dict):
        raise RuntimeError("bea response has no BEAAPI block")
    block = api.get("Results", {})
    if isinstance(block, list):
        block = block[0] if block else {}
    error = api.get("Error") or (block.get("Error") if isinstance(block, dict) else None)
    if error:
        if isinstance(error, dict):
            error = f"{error.get('APIErrorCode', '')} {error.get('APIErrorDescription', '')}".strip()
        raise RuntimeError(f"bea api error {error}")
    if not isinstance(block, dict):
        raise RuntimeError("bea response has no results block")
    return block


# the data rows of a results block. a single row comes back as a bare object
def data_rows(block):
    rows = block.get("Data", [])
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


# one line's rows -> the metrics.csv shape. rows without a usable code, year
# or value are skipped, years before first_year are dropped, and a repeated
# code and year keeps its first value
def parse_data(rows, metric, first_year=FIRST_YEAR):
    records = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = cbsa_code(row.get("GeoFips"))
        year = period_year(row.get("TimePeriod"))
        value = parse_value(row.get("DataValue"))
        if code is None or year is None or value is None or year < first_year:
            continue
        records.append({"cbsa_code": code, "metric": metric, "period": str(year), "value": value})
    df = pd.DataFrame(records, columns=COLUMNS)
    df = df.drop_duplicates(subset=["cbsa_code", "metric", "period"], keep="first")
    return df.sort_values(["cbsa_code", "metric", "period"]).reset_index(drop=True)


# bea reports thousands as unit_mult 3 and dollars as 0. a changed multiplier
# would silently rescale a metric, so it stops the run instead
def check_units(rows, line):
    expected = str(LINES[line]["unit_mult"])
    seen = {str(row.get("UNIT_MULT", "")).strip() for row in rows if isinstance(row, dict)}
    seen.discard("")
    bad = sorted(m for m in seen if m != expected)
    if bad:
        raise RuntimeError(f"bea line {line} reports UNIT_MULT {bad}, expected {expected}")


# the line code list is the source of truth for what each line means. the run
# stops when a line no longer says what its metric claims. descriptions carry
# the table in brackets, and other tables reuse the same keys, so only lines
# tagged for this table count
def verify_line_codes(param_values):
    if isinstance(param_values, dict):
        param_values = [param_values]
    found = {}
    for p in param_values or []:
        if not isinstance(p, dict):
            continue
        key, desc = str(p.get("Key", "")).strip(), str(p.get("Desc", "")).strip()
        tag = TAG.match(desc)
        if tag and tag.group(1).upper() != TABLE:
            continue
        found.setdefault(key, desc)
    problems = []
    for line, spec in LINES.items():
        desc = found.get(line)
        if desc is None:
            problems.append(f"line {line} is missing from the {TABLE} line code list")
            continue
        lowered = desc.lower()
        if spec["phrase"] not in lowered or ("per capita" in lowered) != ("per capita" in spec["phrase"]):
            problems.append(f"line {line} reads '{desc}', expected {spec['phrase']}")
    if problems:
        raise RuntimeError("bea line codes changed: " + "; ".join(problems))
    return {line: found[line] for line in LINES}


# a copy of the response with the data rows before first_year dropped, so the
# committed raw file stays small. everything else in the response is kept
def trim_payload(payload, first_year=FIRST_YEAR):
    trimmed = copy.deepcopy(payload)
    block = results(trimmed)
    block["Data"] = [row for row in data_rows(block)
                     if (period_year(row.get("TimePeriod")) or 0) >= first_year]
    return trimmed


# whole numbers are written without a trailing .0
def format_value(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else repr(value)


def write_metrics(df, path):
    out = df[COLUMNS].copy()
    out["value"] = [format_value(v) for v in out["value"]]
    out.to_csv(path, index=False)
    return path


# one api call. the key rides in the query and never in a message
def _get(key, params):
    query = {"UserID": key, "datasetname": DATASET, "ResultFormat": "json", **params}
    try:
        response = fetch(ENDPOINT, params=query)
    except Exception as e:
        raise RuntimeError(f"bea request failed: {redact(e, key)}") from None
    if not response.ok:
        raise RuntimeError(f"bea returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(f"bea returned a non json body with HTTP {response.status_code}") from None
    try:
        results(payload)
    except RuntimeError as e:
        raise RuntimeError(redact(e, key)) from None
    return payload


# raw responses are committed, so the request echo must not carry the key
def _save(path, payload, key):
    path.write_text(redact(json.dumps(payload, separators=(",", ":")), key) + "\n")
    return path


def _query(**params):
    return ENDPOINT + "?" + "&".join(f"{k}={v}" for k, v in params.items())


def collect():
    key = env_key("BEA_API_KEY")
    if not key:
        print("[bea] BEA_API_KEY is not set, skipping the bea source")
        return None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []

    print(f"[bea] confirming {TABLE} line codes")
    payload = _get(key, {"method": "GetParameterValues", "ParameterName": "LineCode", "TableName": TABLE})
    param_values = results(payload).get("ParamValue", [])
    descriptions = verify_line_codes(param_values)
    path = _save(OUT_DIR / "linecodes.json", payload, key)
    entries.append(manifest_entry(
        path, _query(method="GetParameterValues", datasetname=DATASET, ParameterName="LineCode", TableName=TABLE),
        PROVIDER, f"{TABLE} line codes", TABLE, len(param_values) if isinstance(param_values, list) else 1,
    ))
    print(f"[bea] {len(descriptions)} line codes confirmed -> {path.name}")

    frames, units = [], {}
    for line, spec in LINES.items():
        time.sleep(PAUSE_SECONDS)
        print(f"[bea] fetching {TABLE} line {line}, {spec['phrase']}, every msa")
        payload = _get(key, {"method": "GetData", "TableName": TABLE, "LineCode": line,
                             "GeoFips": "MSA", "Year": "ALL"})
        rows = data_rows(results(payload))
        check_units(rows, line)
        frame = parse_data(rows, spec["metric"])
        frames.append(frame)
        units[line] = next((row.get("CL_UNIT") for row in rows if row.get("CL_UNIT")), None)
        path = _save(OUT_DIR / f"cainc1_line{line}.json", trim_payload(payload), key)
        newest = frame["period"].max() if len(frame) else "none"
        entries.append(manifest_entry(
            path, _query(method="GetData", datasetname=DATASET, TableName=TABLE, LineCode=line,
                         GeoFips="MSA", Year="ALL"),
            PROVIDER, f"{TABLE} line {line}, {descriptions[line]}, metropolitan statistical areas",
            f"{TABLE} line {line} through {newest}", len(frame),
            {"metric": spec["metric"], "unit": units[line], "rows_received": len(rows),
             "rows_kept_from": FIRST_YEAR},
        ))
        print(f"[bea] line {line}: {len(frame)} rows from {FIRST_YEAR} of {len(rows)} received -> {path.name}")

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise RuntimeError(f"bea returned no {TABLE} msa rows from {FIRST_YEAR} onward")
    df = df.sort_values(["cbsa_code", "metric", "period"]).reset_index(drop=True)
    newest = df["period"].max()
    metrics_file = write_metrics(df, OUT_DIR / "metrics.csv")
    entries.insert(0, manifest_entry(
        metrics_file, _query(method="GetData", datasetname=DATASET, TableName=TABLE, GeoFips="MSA", Year="ALL"),
        PROVIDER, "Regional Economic Accounts, CAINC1 personal income summary, metropolitan statistical areas, annual",
        f"{TABLE} {FIRST_YEAR} through {newest}", len(df),
        {"metrics": {spec["metric"]: {"line": line, "unit": units[line], "line_description": descriptions[line]}
                     for line, spec in LINES.items()},
         "cbsa_codes": int(df["cbsa_code"].nunique()), "years": f"{FIRST_YEAR} through {newest}"},
    ))
    write_manifest(OUT_DIR, entries)
    print(f"[bea] {len(df)} rows, {df['cbsa_code'].nunique()} msas, {FIRST_YEAR} through {newest} -> {metrics_file.name}")
    return metrics_file
