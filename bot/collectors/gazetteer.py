import io
import zipfile

import pandas as pd

from bot.common import RAW_DIR, fetch, manifest_entry, write_manifest

YEAR = 2024
URL = f"https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{YEAR}_Gazetteer/{YEAR}_Gaz_cbsa_national.zip"
OUT_DIR = RAW_DIR / "gazetteer"
OUT_FILE = OUT_DIR / "cbsa_centroids.csv"

KEEP = {
    "GEOID": "cbsa_code",
    "NAME": "name",
    "CBSA_TYPE": "cbsa_type",  # 1 = metro, 2 = micro
    "ALAND_SQMI": "land_sqmi",
    "INTPTLAT": "lat",
    "INTPTLONG": "lon",
}


# the txt inside the zip is tab separated and every line has trailing spaces
def parse_gazetteer(text):
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
    df = pd.DataFrame(rows)[list(KEEP)].rename(columns=KEEP)
    for col in ("lat", "lon", "land_sqmi"):
        df[col] = df[col].astype(float)
    df["cbsa_type"] = df["cbsa_type"].astype(int)
    return df


def collect():
    print(f"[gazetteer] fetching {YEAR} cbsa centroids")
    response = fetch(URL)
    response.raise_for_status()

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    text = archive.read(archive.namelist()[0]).decode("latin-1")
    df = parse_gazetteer(text)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_FILE, index=False)
    write_manifest(OUT_DIR, [manifest_entry(
        OUT_FILE, URL, "U.S. Census Bureau",
        f"{YEAR} Gazetteer, core based statistical areas, internal point coordinates",
        f"{YEAR} Gazetteer", len(df),
    )])
    print(f"[gazetteer] {len(df)} cbsas -> {OUT_FILE.name}")
    return OUT_FILE
