# is477-sp26 workflow
# does the same as run_all.py but tracks file deps so it only re-runs what changed

import json
import sys
from pathlib import Path

# python that started snakemake. same one runs each rule
PYTHON = sys.executable

# acs end years come from the pinned vintages file so the dag matches what the
# downloader writes. the fallback only applies before the first pin exists
VINTAGES_FILE = Path("data/raw/census/vintages.json")
if VINTAGES_FILE.exists():
    CENSUS_YEARS = json.loads(VINTAGES_FILE.read_text())["years"]
else:
    CENSUS_YEARS = [2014, 2019, 2024]


# rule all = the final outputs we want
rule all:
    input:
        "data/integrated/hpi_census_merged.csv",
        "results/visualizations/hpi_distribution.png",
        "results/visualizations/income_vs_hpi.png",
        "results/visualizations/homeownership_vs_hpi.png",
        "results/visualizations/top15_metros_hpi.png",
        "results/visualizations/correlation_matrix.png"


# pull fhfa files and write manifest
rule download_fhfa:
    output:
        "data/raw/fhfa/hpi_master.csv",
        "data/raw/fhfa/hpi_exp_metro.txt",
        "data/raw/fhfa/download_manifest.json"
    shell:
        f"{PYTHON} scripts/download_fhfa.py"


# pull the pinned acs vintages, build combined csv, write manifest
rule download_census:
    output:
        expand("data/raw/census/acs_5yr_{year}.csv", year=CENSUS_YEARS),
        "data/raw/census/acs_5yr_combined.csv",
        "data/raw/census/download_manifest.json"
    shell:
        f"{PYTHON} scripts/download_census.py"


# load both, clean, merge on cbsa+year, write csv and 5 charts
rule integrate:
    input:
        "data/raw/fhfa/hpi_master.csv",
        "data/raw/census/acs_5yr_combined.csv"
    output:
        "data/integrated/hpi_census_merged.csv",
        "results/visualizations/hpi_distribution.png",
        "results/visualizations/income_vs_hpi.png",
        "results/visualizations/homeownership_vs_hpi.png",
        "results/visualizations/top15_metros_hpi.png",
        "results/visualizations/correlation_matrix.png"
    shell:
        f"{PYTHON} scripts/eda_integrate.py"
