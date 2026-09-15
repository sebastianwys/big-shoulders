import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
INTEGRATED = BASE_DIR / "data" / "integrated" / "hpi_census_merged.csv"
WEB_DATA_DIR = BASE_DIR / "web" / "public" / "data"

# identify the bot to every source. polite, and it makes us easy to contact
USER_AGENT = "loop-bot/0.1 (+https://github.com/sebastianwys/loop)"

# the study years, same as the census vintages
STUDY_YEARS = [2014, 2019, 2024]


# every collector fetches through here so the timeout, retry and user agent
# policy live in one place. retries on connection errors and 5xx only
def fetch(url, params=None, json_body=None, timeout=120, retries=3):
    headers = {"User-Agent": USER_AGENT}
    last_error = None
    for attempt in range(retries):
        try:
            if json_body is not None:
                response = requests.post(url, json=json_body, timeout=timeout, headers=headers)
            else:
                response = requests.get(url, params=params, timeout=timeout, headers=headers)
            if response.status_code < 500:
                return response
            last_error = RuntimeError(f"HTTP {response.status_code}")
        except requests.RequestException as e:
            last_error = e
        time.sleep(2 ** attempt)
    raise last_error


def env_key(var):
    return os.environ.get(var, "").strip()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# same chunked hash as the pipeline scripts
def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


# same manifest shape as data/raw/fhfa and data/raw/census
def manifest_entry(path, endpoint, provider, dataset, version, row_count, notes=None):
    entry = {
        "filename": path.name,
        "file_format": path.suffix.lstrip(".").upper(),
        "source": {
            "endpoint": endpoint,
            "provider": provider,
            "access_method": "REST API" if "api." in endpoint else "Direct HTTP download",
            "dataset": dataset,
        },
        "integrity": {
            "sha256": sha256_file(path),
            "size_kb": round(path.stat().st_size / 1024, 1),
            "row_count": row_count,
        },
        "version": version,
        "downloaded_at": utc_now(),
    }
    if notes:
        entry["notes"] = notes
    return entry


def write_manifest(folder, entries):
    path = folder / "download_manifest.json"
    path.write_text(json.dumps(entries, indent=2) + "\n")
    return path
