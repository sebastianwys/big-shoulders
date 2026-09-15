import json
import re
from pathlib import Path

import pandas as pd

from bot.collectors.gazetteer import YEAR as GAZETTEER_YEAR
from bot.common import INTEGRATED, RAW_DIR, STUDY_YEARS, WEB_DATA_DIR, utc_now

DEFAULT_PATHS = {
    "merged": INTEGRATED,
    "centroids": RAW_DIR / "gazetteer" / "cbsa_centroids.csv",
    "zhvi": RAW_DIR / "zillow" / "zhvi_metro.csv",
    "zori": RAW_DIR / "zillow" / "zori_metro.csv",
    "bls": RAW_DIR / "bls" / "laus_metro_unemployment.csv",
    "fred": RAW_DIR / "fred" / "mortgage30us.csv",
}

# zillow monthly columns look like 2024-01-31
MONTH = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# census marks a missing estimate with a large negative sentinel
SENTINEL = -666666

NUMERIC = [
    "year", "avg_index_nsa", "median_income", "total_pop", "median_age",
    "bachelors_count", "masters_count", "total_occupied_units",
    "owner_occupied_units", "median_home_value", "homeownership_rate",
]


def missing(value):
    return value is None or pd.isna(value)


# none stays none, everything else becomes a rounded python float
def rnd(value, digits):
    return None if missing(value) else round(float(value), digits)


def as_int(value):
    return None if missing(value) else int(round(float(value)))


# (later - earlier) / earlier. none if either side is missing or earlier is 0
def growth(later, earlier):
    if missing(later) or missing(earlier) or earlier == 0:
        return None
    return (later - earlier) / earlier


def ratio(numerator, denominator):
    if missing(numerator) or missing(denominator) or denominator == 0:
        return None
    return numerator / denominator


# --- loaders ---

def load_merged(path):
    df = pd.read_csv(path, dtype={"cbsa_code": str, "place_id": str, "geo_level": str, "parent_cbsa": str})
    for col in NUMERIC:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].mask(df[col] <= SENTINEL)
    return df


def load_centroids(path):
    df = pd.read_csv(path, dtype={"cbsa_code": str})
    return df.drop_duplicates("cbsa_code").set_index("cbsa_code")


# one row per metro indexed by zillow's own name, monthly columns only
def load_zillow(path):
    df = pd.read_csv(path)
    df = df[df["RegionType"] != "country"]
    df = df[~df["RegionName"].duplicated()].set_index("RegionName")
    months = [c for c in df.columns if MONTH.match(c)]
    return df[months].apply(pd.to_numeric, errors="coerce")


def load_bls(path):
    df = pd.read_csv(path, dtype={"cbsa_code": str, "period": str})
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def load_fred(path):
    df = pd.read_csv(path, dtype={"date": str})
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


# --- zillow ---

# fhfa says "Chicago-Naperville-Elgin, IL-IN-WI", zillow says "Chicago, IL".
# exact name first, then first city, then first two cities
def zillow_candidates(place_name):
    if "," not in place_name:
        return [place_name]
    cities, states = [part.strip() for part in place_name.split(",", 1)]
    state_tokens = states.replace("-", " ").split()
    first_state = state_tokens[0] if state_tokens else ""
    # "/" separates a city from its county name, as in louisville/jefferson county
    parts = [part.strip() for part in cities.replace("/", "-").split("-")]
    candidates = [place_name, f"{parts[0]}, {first_state}"]
    if len(parts) > 1:
        candidates.append(f"{parts[0]}-{parts[1]}, {first_state}")
    # zillow sometimes names a metro by a later city, "The Villages, FL" for
    # "Wildwood-The Villages, FL". first city stays preferred by order
    candidates += [f"{part}, {first_state}" for part in parts[1:]]
    return list(dict.fromkeys(candidates))


# fhfa marks divisions with a suffix the map does not need
def display_name(place_name):
    return re.sub(r"\s*\(MSAD\)$", "", str(place_name)).strip()


# the parent metro of a division, named without the census suffix
def parent_info(parent_code, centroids):
    code = None if missing(parent_code) else str(parent_code).strip()
    if not code or code not in centroids.index:
        return None
    name = re.sub(r"\s*(Metro|Micro) Area$", "", str(centroids.loc[code]["name"]))
    return {"cbsa": code, "name": name}


def match_zillow(place_name, frame):
    if frame is None or place_name is None:
        return None
    for candidate in zillow_candidates(place_name):
        if candidate in frame.index:
            return frame.loc[candidate]
    return None


# mean of the non-null months in one year
def zillow_annual(row, year):
    if row is None:
        return None
    values = row[[c for c in row.index if c.startswith(f"{year}-")]].dropna()
    return float(values.mean()) if len(values) else None


# last non-null month and its date
def zillow_latest(row):
    if row is None:
        return None, None
    values = row.dropna()
    if not len(values):
        return None, None
    return float(values.iloc[-1]), str(values.index[-1])


# --- bls ---

# annual average is period m13
def bls_year(frame, cbsa, year):
    if frame is None:
        return None
    rows = frame[(frame["cbsa_code"] == cbsa) & (frame["period"] == "M13") & (frame["year"] == year)]
    values = rows["value"].dropna()
    return float(values.iloc[0]) if len(values) else None


# newest monthly row, date as yyyy-mm
def bls_latest(frame, cbsa):
    if frame is None:
        return None, None
    rows = frame[(frame["cbsa_code"] == cbsa) & (frame["period"] != "M13")].dropna(subset=["value"])
    if not len(rows):
        return None, None
    newest = rows.sort_values(["year", "period"]).iloc[-1]
    return float(newest["value"]), f"{int(newest['year'])}-{str(newest['period'])[1:]}"


# --- fred ---

def fred_annual(frame, year):
    if frame is None:
        return None
    values = frame[frame["date"].str.startswith(str(year))]["value"].dropna()
    return float(values.mean()) if len(values) else None


def fred_latest(frame):
    if frame is None:
        return None, None
    rows = frame.dropna(subset=["value"])
    if not len(rows):
        return None, None
    last = rows.iloc[-1]
    return float(last["value"]), str(last["date"])


# --- assembly ---

def year_record(row, zhvi_row, zori_row, bls_frame, cbsa, year):
    get = (lambda col: None) if row is None else (lambda col: row.get(col))
    pop = get("total_pop")
    bachelors, masters = get("bachelors_count"), get("masters_count")
    degree = None if missing(bachelors) or missing(masters) else ratio(bachelors + masters, pop)
    own_rate = get("homeownership_rate")
    if missing(own_rate):
        own_rate = ratio(get("owner_occupied_units"), get("total_occupied_units"))
    return {
        "hpi": rnd(get("avg_index_nsa"), 2),
        "income": rnd(get("median_income"), 1),
        "pop": as_int(pop),
        "age": rnd(get("median_age"), 1),
        "degree_share": rnd(degree, 4),
        "own_rate": rnd(own_rate, 4),
        "home_value": rnd(get("median_home_value"), 1),
        "zhvi": rnd(zillow_annual(zhvi_row, year), 1),
        "zori": rnd(zillow_annual(zori_row, year), 1),
        "unemp": rnd(bls_year(bls_frame, cbsa, year), 1),
    }


def build_metros(merged, centroids, zhvi=None, zori=None, bls_frame=None):
    metros, dropped, unmatched = [], 0, 0
    y0, y1, y2 = STUDY_YEARS
    for cbsa, group in merged.groupby("cbsa_code", sort=False):
        if cbsa not in centroids.index:
            dropped += 1
            continue
        name = display_name(group["place_name"].iloc[0])
        centroid = centroids.loc[cbsa]
        rows = {int(r["year"]): r for _, r in group.iterrows()}

        first = group.iloc[0]
        level = "division" if str(first.get("geo_level", "")) == "division" else "msa"
        parent = parent_info(first.get("parent_cbsa"), centroids) if level == "division" else None

        # zillow publishes metros, not divisions, so a division carries its
        # parent's values and says so. a division with no parent gets nothing,
        # since "Boston, MA" the division would otherwise match the metro silently
        zillow_name = parent["name"] if parent else (name if level == "msa" else None)
        zhvi_row = match_zillow(zillow_name, zhvi)
        zori_row = match_zillow(zillow_name, zori)
        zillow_scope = None if zhvi_row is None else ("parent metro" if parent else "metro")
        if zhvi is not None and zhvi_row is None:
            unmatched += 1

        def value(year, col):
            row = rows.get(year)
            return None if row is None else row.get(col)

        zhvi_latest, zhvi_date = zillow_latest(zhvi_row)
        zori_latest, zori_date = zillow_latest(zori_row)
        unemp_latest, unemp_date = bls_latest(bls_frame, cbsa)

        metros.append({
            "cbsa": cbsa,
            "name": name,
            "level": level,
            "parent": parent,
            "zillow_scope": zillow_scope,
            "lat": float(centroid["lat"]),
            "lon": float(centroid["lon"]),
            "years": {str(y): year_record(rows.get(y), zhvi_row, zori_row, bls_frame, cbsa, y) for y in STUDY_YEARS},
            "latest": {
                "zhvi": rnd(zhvi_latest, 1), "zhvi_date": zhvi_date,
                "zori": rnd(zori_latest, 1), "zori_date": zori_date,
                "unemp": rnd(unemp_latest, 1), "unemp_date": unemp_date,
            },
            "growth": {
                f"hpi_{y0 % 100}_{y1 % 100}": rnd(growth(value(y1, "avg_index_nsa"), value(y0, "avg_index_nsa")), 4),
                f"hpi_{y1 % 100}_{y2 % 100}": rnd(growth(value(y2, "avg_index_nsa"), value(y1, "avg_index_nsa")), 4),
                f"income_{y0 % 100}_{y2 % 100}": rnd(growth(value(y2, "median_income"), value(y0, "median_income")), 4),
                f"pop_{y0 % 100}_{y2 % 100}": rnd(growth(value(y2, "total_pop"), value(y0, "total_pop")), 4),
                f"home_value_{y0 % 100}_{y2 % 100}": rnd(growth(value(y2, "median_home_value"), value(y0, "median_home_value")), 4),
            },
            "ptir": {str(y): rnd(ratio(value(y, "median_home_value"), value(y, "median_income")), 4) for y in STUDY_YEARS},
        })

    metros.sort(key=lambda m: m["name"])
    return metros, dropped, unmatched


def zillow_version(frame):
    return None if frame is None or not len(frame.columns) else f"through {frame.columns[-1]}"


def bls_version(frame):
    return None if frame is None or not len(frame) else f"{int(frame['year'].min())} onward"


def fred_version(frame):
    _, date = fred_latest(frame)
    return None if date is None else f"through {date}"


def national_block(fred_frame):
    if fred_frame is None:
        return None
    latest, date = fred_latest(fred_frame)
    block = {str(y): rnd(fred_annual(fred_frame, y), 2) for y in STUDY_YEARS}
    block["latest"] = rnd(latest, 2)
    block["latest_date"] = date
    return {"mortgage_rate": block}


# optional inputs come back as none with a note instead of failing the build
def optional(path, loader, label):
    path = Path(path)
    if not path.exists():
        print(f"[build] {label} not found at {path.name}, its fields will be null")
        return None
    return loader(path)


def build(out_path=None, paths=None):
    p = dict(DEFAULT_PATHS)
    if paths:
        p.update(paths)

    merged = load_merged(p["merged"])
    centroids = load_centroids(p["centroids"])
    zhvi = optional(p["zhvi"], load_zillow, "zillow zhvi")
    zori = optional(p["zori"], load_zillow, "zillow zori")
    bls_frame = optional(p["bls"], load_bls, "bls")
    fred_frame = optional(p["fred"], load_fred, "fred")

    metros, dropped, unmatched = build_metros(merged, centroids, zhvi, zori, bls_frame)

    payload = {
        "generated_at": utc_now(),
        "years": list(STUDY_YEARS),
        "sources": {
            "gazetteer": f"{GAZETTEER_YEAR} Gazetteer",
            "zillow": zillow_version(zhvi),
            "bls": bls_version(bls_frame),
            "fred": fred_version(fred_frame),
        },
        "national": national_block(fred_frame),
        "metros": metros,
    }

    out_path = Path(out_path) if out_path else WEB_DATA_DIR / "metros.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=True, allow_nan=False) + "\n")

    print(f"[build] {len(metros)} metros, {dropped} without a centroid dropped, "
          f"{unmatched} without a zillow match -> {out_path.name} ({out_path.stat().st_size / 1024:.0f} KB)")
    return out_path


if __name__ == "__main__":
    build()
