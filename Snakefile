# is477-sp26 workflow
# does the same as run_all.py but tracks file deps so it only re-runs what changed

import sys

# python that started snakemake. same one runs each rule
PYTHON = sys.executable


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


# pull 3 acs vintages, build combined csv, write manifest
rule download_census:
    output:
        "data/raw/census/acs_5yr_2014.csv",
        "data/raw/census/acs_5yr_2019.csv",
        "data/raw/census/acs_5yr_2024.csv",
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
