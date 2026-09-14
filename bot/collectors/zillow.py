from bot.common import RAW_DIR, fetch, manifest_entry, write_manifest

OUT_DIR = RAW_DIR / "zillow"
BASE = "https://files.zillowstatic.com/research/public_csvs"

# metro level, monthly. zhvi is the mid tier home value index, zori is rent
FILES = {
    "zhvi_metro.csv": (
        f"{BASE}/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
        "ZHVI, all homes, mid tier, smoothed, seasonally adjusted, monthly, metro",
    ),
    "zori_metro.csv": (
        f"{BASE}/zori/Metro_zori_uc_sfrcondomfr_sm_month.csv",
        "ZORI, all homes plus multifamily, smoothed, monthly, metro",
    ),
}

ATTRIBUTION = "Data provided by Zillow Research (zillow.com/research/data). Zillow terms of use apply."


def collect():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for filename, (url, dataset) in FILES.items():
        print(f"[zillow] fetching {filename}")
        response = fetch(url)
        response.raise_for_status()

        path = OUT_DIR / filename
        path.write_bytes(response.content)

        # last column header is the newest month, which is the file's version
        header = response.content.split(b"\n", 1)[0].decode()
        newest_month = header.rsplit(",", 1)[-1].strip()
        row_count = response.content.count(b"\n") - 1

        entries.append(manifest_entry(path, url, "Zillow Research", dataset,
                                      f"through {newest_month}", row_count, ATTRIBUTION))
        print(f"[zillow] {row_count} rows through {newest_month} -> {filename}")

    write_manifest(OUT_DIR, entries)
    return OUT_DIR
