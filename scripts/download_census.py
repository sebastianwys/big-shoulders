import requests
import pandas as pd
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "census"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.census.gov/data/{year}/acs/acs5"

# add codes here to pull more columns
# B19013_001E = median household income
# B01003_001E = total population
# B01002_001E = median age
# B15003_022E = bachelors degree count
# B15003_023E = masters degree count
# B25003_001E = total occupied housing units
# B25003_002E = owner occupied housing units
# B25077_001E = median home value
VARIABLES = [
    "NAME",
    "B19013_001E",
    "B01003_001E",
    "B01002_001E",
    "B15003_022E",
    "B15003_023E",
    "B25003_001E",
    "B25003_002E",
    "B25077_001E",
]

# non-overlapping 5-year windows. 2014=2010-2014, 2019=2015-2019, 2024=2020-2024
# 2010 dropped, api errors for that vintage
YEARS = [2014, 2019, 2024]


# same chunked hash as fhfa
def compute_sha256(filepath):
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


# pull one year from the api. everything comes back as strings
def fetch_acs_data(year):
    print(f"Fetching ACS 5-year data for {year}...")

    url = BASE_URL.format(year=year)
    params = {
        "get": ",".join(VARIABLES),
        "for": "metropolitan statistical area/micropolitan statistical area:*"  # * = all msas
    }

    response = requests.get(url, params=params)
    response.raise_for_status()

    data = response.json()
    headers = data[0]  # row 0 is column names
    rows = data[1:]

    df = pd.DataFrame(rows, columns=headers)
    df["year"] = year  # tag rows so we know the vintage after concat

    return df


# remove stale years, pull fresh data, write combined csv and manifest
def main():
    # if YEARS changed, drop old per-year csvs
    for stale in RAW_DIR.glob("acs_5yr_*.csv"):
        year_str = stale.stem.replace("acs_5yr_", "")
        if year_str.isdigit() and int(year_str) not in YEARS:
            stale.unlink()
            print(f"Removed stale file: {stale.name}")

    manifest = []
    all_frames = []

    for year in YEARS:
        try:
            df = fetch_acs_data(year)
            all_frames.append(df)

            filename = f"acs_5yr_{year}.csv"
            filepath = RAW_DIR / filename
            df.to_csv(filepath, index=False)

            checksum = compute_sha256(filepath)
            size_kb = filepath.stat().st_size / 1024

            print(f"  Saved {filepath} ({len(df)} rows, {size_kb:.1f} KB)")
            print(f"  SHA-256: {checksum}")

            manifest.append({
                "filename": filename,
                "file_format": "CSV",
                "source": {
                    "endpoint": BASE_URL.format(year=year),
                    "provider": "U.S. Census Bureau",
                    "access_method": "REST API",
                    "dataset": "ACS 5-year estimates",
                    "geography": "metropolitan statistical area/micropolitan statistical area:*",
                    "variables": VARIABLES
                },
                "integrity": {
                    "sha256": checksum,
                    "size_kb": round(size_kb, 1),
                    "row_count": len(df)
                },
                "version": f"ACS 5-year {year}",
                "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            })

        except Exception as e:
            # type(e).__name__ tells you what kind of failure
            print(f"  ERROR {year}: {type(e).__name__}: {e}")
            print(f"  Endpoint: {BASE_URL.format(year=year)}")
            print(f"  Variables attempted: {VARIABLES}")
            print(f"  This vintage may have different variable codes. Skipping.")

    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined_path = RAW_DIR / "acs_5yr_combined.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined file: {combined_path} ({len(combined)} total rows)")

    manifest_path = RAW_DIR / "download_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Manifest saved to {manifest_path}")
    print("Census ACS download complete.")


if __name__ == "__main__":
    main()
