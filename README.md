# Project Big Shoulders

**Housing Affordability Trend Analysis**
Integrating the FHFA House Price Index with U.S. Census ACS data across U.S. metropolitan areas.

IS477 Spring 2026 final project.

## Contributors

Sebastian Wysocki. Working individually (approved). University of Illinois Urbana-Champaign. sebaj1011@gmail.com.

Sole contributor. All commits in the Git history are mine. Responsible for dataset selection, acquisition scripts, EDA, integration, cleaning, visualizations, and documentation.

---

## Summary

Home prices do not move in isolation. They respond to local income, population, age, and education. This project asks: which of those drivers actually predict housing price changes, and which metros have broken away from those baselines.

To answer that, the project builds a reproducible pipeline that pulls two government datasets, profiles them, cleans them, integrates them on metro codes, and produces visualizations.

```
DATASET 1                       DATASET 2
FHFA House Price Index          U.S. Census ACS 5-year
Direct CSV download             REST API
1975 to 2026                    3 vintages: 2014, 2019, 2024
Public domain                   Public domain
```

The Census pull uses three non-overlapping windows so each snapshot is statistically independent.

```
2010 ----- 2014        2015 ----- 2019        2020 ----- 2024
   recession recovery     pre-COVID peak        post-COVID
```

The integrated dataset is 1,101 rows across 373 metros and three years. Five visualizations live in `results/visualizations/`.

The headline finding is a regime shift between the 2019 and 2024 vintages. The 2022 top-15 list (Austin, Salt Lake City, Denver, Boise, Phoenix) was Western tech metros. The 2024 top-15 list is led by Bozeman, MT, with Charleston, Naples, San Jose, and San Diego rounding out the top five. Mountain towns and Sun Belt coastal markets replaced urban tech centers, which is the visible signature of remote-work migration.

The numerical version of that story is a correlation matrix. Population correlation with HPI dropped from about 0.40 to 0.23. Smaller amenity-rich metros now drive price appreciation, and metro size has become a weaker predictor.

The reproducibility infrastructure includes SHA-256 checksums for every download, structured manifests with source endpoints and ISO 8601 UTC timestamps, an empty-merge guard, stale-file cleanup, and a single `run_all.py` script. The MIT license covers source code. The data is public domain.

This is the IS477 course deliverable. The ML and scenario modeling work continues post-course in a separate repository (see Future Work).

---

## Pipeline Overview

```
+---------------------------+
| scripts/download_fhfa.py  |  ---->  data/raw/fhfa/
+---------------------------+         hpi_master.csv + manifest
              |
              v
+---------------------------+
| scripts/download_census.py|  ---->  data/raw/census/
+---------------------------+         3 vintages + combined + manifest
              |
              v
+---------------------------+
| scripts/eda_integrate.py  |  ---->  data/integrated/hpi_census_merged.csv
+---------------------------+         results/visualizations/ (5 PNGs)

Two runners wrap the three scripts above:
   Snakefile     DAG-based, incremental rebuilds (recommended)
   run_all.py    Python subprocess wrapper, always runs all three
```

## Storage and Organization

This project uses a tabular data model. All raw and integrated datasets are CSV. JSON manifests track integrity and provenance. PNG files store visualizations.

### File Types

| Type | Used for |
| --- | --- |
| CSV | All raw and integrated tabular data |
| JSON | Per-source download manifests with SHA-256, source URLs, timestamps, version tags |
| TXT | One FHFA expanded metro file (kept in original format) |
| PNG | Five visualizations |
| MD | All documentation |
| JSONLD | Schema.org Dataset metadata (`metadata.jsonld`) |

### Directory Layout

```
IS477-SP26/
├── scripts/                      acquisition + integration scripts
├── data/
│   ├── raw/
│   │   ├── fhfa/                 pulled from FHFA + manifest
│   │   └── census/               pulled from Census API + manifest
│   └── integrated/               merged output (final dataset)
├── results/
│   └── visualizations/           5 PNG charts
├── README.md                     project report
├── ProjectPlan.md                milestone 2 deliverable
├── StatusReport.md               milestone 3 deliverable
├── LICENSE                       MIT for code, public domain for data
├── metadata.jsonld               Schema.org Dataset description
├── Snakefile                     workflow definition (recommended)
├── run_all.py                    simple Python wrapper
└── requirements.txt              pinned dependencies
```

### Naming Conventions

- Raw files keep their source name (`hpi_master.csv`, `acs_5yr_2024.csv`)
- Integrated outputs use compound names showing the join (`hpi_census_merged.csv`)
- Manifests are always `download_manifest.json` inside each source folder
- Visualizations use snake_case descriptive names
- Per-vintage Census files use the four-digit vintage year suffix (`acs_5yr_YYYY.csv`)

### Why This Strategy

CSV is human-readable, version-controllable, and works with pandas directly. The dataset is small enough that no relational database is needed. Per-source folders keep raw files separated from derived files. Manifests live next to the data they describe.

---

## Data Lifecycle

This project follows the DCC (Digital Curation Centre) Curation Lifecycle Model. Each phase maps to a specific artifact in the repo.

| DCC Phase | This Project |
| --- | --- |
| Conceptualise | `ProjectPlan.md` defines research questions and dataset selection |
| Create or Receive | `scripts/download_fhfa.py`, `scripts/download_census.py` |
| Appraise and Select | Filter to MSA, quarterly, traditional, all-transactions |
| Ingest | Save to `data/raw/` with SHA-256 manifest |
| Preservation Action | Public domain inputs, MIT license, structured manifests |
| Store | `data/raw/` and `data/integrated/` committed to GitHub |
| Access, Use, Reuse | `README.md`, `Snakefile`, `run_all.py`, `metadata.jsonld` |
| Transform | `scripts/eda_integrate.py` cleans, joins, derives, visualizes |

The pipeline can re-execute when upstream sources update. The SHA-256 mechanism flags when this happens so downstream stages re-run only when inputs actually changed.

---

## Data Profile

### Ethical, Legal, Policy

Both datasets are U.S. government works in the public domain.

| Concern | Status |
| --- | --- |
| Personally identifiable information | None. Smallest unit is metro area. |
| Consent | Not applicable. ACS is mandatory under Title 13 USC. FHFA is aggregated mortgage data. |
| Copyright | None. Public domain (17 USC 105). |
| License | MIT for code (`LICENSE`). Data is unrestricted. |

### FHFA House Price Index

The U.S. government's official measure of single-family home value changes. Weighted repeat-sales methodology applied to mortgage transaction data from Fannie Mae, Freddie Mac, FHA, and VA loans.

| Field | Value |
| --- | --- |
| Location | `data/raw/fhfa/hpi_master.csv` |
| Source | https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv |
| Provider | Federal Housing Finance Agency |
| Access | Direct HTTP download |
| License | Public domain |
| Format | CSV, ~12.9 MB, ~133,000 rows (FHFA updates monthly) |
| Manifest | `data/raw/fhfa/download_manifest.json` |

After filtering to the canonical inter-metro index (MSA, quarterly, traditional, all-transactions), the working slice is 70,243 rows across 410 unique MSAs.

#### Data Dictionary (used columns)

| Column | Type | Description |
| --- | --- | --- |
| `place_id` | string | CBSA code. Joins to Census `cbsa_code`. |
| `place_name` | string | Metro name. |
| `hpi_type` | string | Filtered to `traditional`. |
| `hpi_flavor` | string | Filtered to `all-transactions`. |
| `level` | string | Filtered to `MSA`. |
| `frequency` | string | Filtered to `quarterly`. |
| `yr` | int | Year of observation. |
| `period` | int | Quarter (1-4). |
| `index_nsa` | float | Non-seasonally adjusted HPI. **Primary measure.** |
| `index_sa` | float | Seasonally adjusted HPI. 100% null at MSA level. Not used. |

### Census ACS 5-Year Estimates

The Census Bureau pools 60 months of survey responses into one statistically reliable estimate at the MSA level. Three non-overlapping vintages.

| Vintage | Survey Window | Role | File | Rows |
| --- | --- | --- | --- | --- |
| 2014 | 2010-2014 | Post-recession baseline | `acs_5yr_2014.csv` | 929 |
| 2019 | 2015-2019 | Pre-COVID peak | `acs_5yr_2019.csv` | 938 |
| 2024 | 2020-2024 | Post-COVID reality | `acs_5yr_2024.csv` | 935 |
| Combined | All three | Used in merge | `acs_5yr_combined.csv` | 2,802 |

| Field | Value |
| --- | --- |
| Source | `https://api.census.gov/data/{year}/acs/acs5` |
| Provider | U.S. Census Bureau |
| Access | REST API (JSON) |
| License | Public domain |
| Geography | All MSAs and micropolitan statistical areas |
| Manifest | `data/raw/census/download_manifest.json` |

#### Data Dictionary (renamed columns)

| Original | Renamed | Type | Description |
| --- | --- | --- | --- |
| `NAME` | `NAME` | string | Metro name. |
| (geo) | `cbsa_code` | string | CBSA code. **Cast from int to string for join.** |
| `B19013_001E` | `median_income` | float | Median household income (USD). |
| `B01003_001E` | `total_pop` | float | Total population. |
| `B01002_001E` | `median_age` | float | Median age. |
| `B15003_022E` | `bachelors_count` | float | Bachelor's degree holders. |
| `B15003_023E` | `masters_count` | float | Master's degree holders. |
| `B25003_001E` | `total_occupied_units` | float | Total occupied housing units. |
| `B25003_002E` | `owner_occupied_units` | float | Owner-occupied units. |
| `B25077_001E` | `median_home_value` | float | Median home value (USD). |
| derived | `homeownership_rate` | float | `owner / total`. |
| added | `year` | int | Vintage tag. |

### Schema (How the Two Datasets Connect)

```
+-------------------------+         +-------------------------+
|       FHFA HPI          |         |      CENSUS ACS         |
|-------------------------|         |-------------------------|
|  PK   place_id          |         |  PK   cbsa_code         |
|       place_name        |         |  PK   year              |
|       hpi_type          |         |       NAME              |
|       hpi_flavor        |         |       median_income     |
|       level             |         |       total_pop         |
|       frequency         |         |       median_age        |
|  PK   yr                |         |       bachelors_count   |
|       period            |         |       masters_count     |
|       index_nsa         |         |       total_occupied    |
|       index_sa          |         |       owner_occupied    |
+-------------------------+         |       median_home_value |
            |                       +-------------------------+
            |                                    |
            |  inner join on                     |
            |  (place_id, yr) = (cbsa_code, year)|
            +--------------+---------------------+
                           |
                           v
            +-------------------------+
            |    INTEGRATED CSV       |
            |-------------------------|
            |  place_id, yr (keys)    |
            |  + FHFA columns         |
            |  + Census columns       |
            |  + homeownership_rate   |
            +-------------------------+
                  1101 rows
                  373 unique metros
                  years: 2014, 2019, 2024
```

The join is type-cast on the Census side: `cbsa_code` is converted from int to string before the merge to match FHFA's string format.

### Integrated Dataset

| Field | Value |
| --- | --- |
| Location | `data/integrated/hpi_census_merged.csv` |
| Rows | 1,101 |
| Columns | 19 |
| Unique metros | 373 |
| Years | 2014, 2019, 2024 |
| Join | Inner join on (`place_id`, `yr`) and (`cbsa_code`, `year`) |

---

## Data Quality

Five quality dimensions checked. Profile output is captured in script logs.

| Dimension | Result | Action Taken |
| --- | --- | --- |
| FHFA completeness | `index_nsa`: 0 nulls. `index_sa`: 100% nulls. | Use `index_nsa`. SA index not published at MSA level. |
| Census completeness | <1% suppressed values per variable. | Coerce sentinel `-666666666` to NaN with `pd.to_numeric`. |
| Type consistency | FHFA stores codes as strings. Census returns ints. Initial merge: 0 overlap. | Cast Census `cbsa_code` to string before join. |
| Geographic coverage | 410 FHFA codes vs 1,010 Census codes. Overlap: 373. | 37 unmatched FHFA metros are likely metropolitan divisions. Crosswalk deferred to post-course work. |
| Temporal coverage | FHFA 1975-2026. Census 3 vintages. | Inner join restricts to vintage years. 1,101 rows of theoretical 1,119 (373 x 3). |

A `download_manifest.json` for each dataset records filename, source, SHA-256 checksum, file size, row count, vintage, and ISO 8601 UTC timestamp. A re-download with a different hash is the trigger to re-run downstream stages.

---

## Data Cleaning

Five operations applied across the pipeline.

**1. FHFA series lock.** Filter to `level == "MSA"` and `frequency == "quarterly"` and `hpi_type == "traditional"` and `hpi_flavor == "all-transactions"`. Without this lock, multiple HPI variants survived into the annual aggregation and duplicated Census rows on the merge.

| Before fix | After fix |
| --- | --- |
| 3.77 rows per metro | 2.95 rows per metro |
| Inflated by duplication | Close to expected 3 (years per metro) |

**2. Quarterly to annual.** Collapse FHFA quarterly observations to annual averages per metro. `groupby([place_id, place_name, hpi_type, hpi_flavor, yr])` then `mean()` of `index_nsa`. A `quarters_available` count flags incomplete years.

**3. Census numeric conversion.** The API returns everything as strings. Coerce eight numeric variables with `pd.to_numeric(errors="coerce")`. The Census suppression sentinel `-666666666` and any non-numeric values become NaN.

**4. CBSA type cast.** `census["cbsa_code"] = census["cbsa_code"].astype(str)`. One line. Restored full geographic overlap.

**5. Derived columns.** `homeownership_rate = owner_occupied_units / total_occupied_units`. Normalized rate is more comparable across metros than absolute counts.

The merge is an inner join. An empty-merge guard raises `RuntimeError` if it produces zero rows, which catches CBSA boundary drift before bad data reaches downstream.

---

## Findings

The integrated 2024 vintage shows a regime shift in metropolitan housing markets compared with the 2022-vintage baseline.

**Top-15 list inversion.**

| 2022 vintage (prior) | 2024 vintage (current) |
| --- | --- |
| Austin, Salt Lake, Denver | Bozeman MT (615), Charleston SC, Naples FL |
| Boise, Phoenix, Portland | San Jose CA, San Diego CA, Bend OR |
| Western tech metros dominant | Mountain towns + Sun Belt coastal dominant |

Austin and Denver dropped to mid-rank. Salt Lake, Boise, Portland fell off the top 15 entirely. Two Montana metros (Bozeman and Missoula) appear in the top 15.

**Population-HPI decoupling.**

```
2022 vintage: corr(population, HPI) ~= 0.40
2024 vintage: corr(population, HPI) ~= 0.23
```

Smaller amenity-rich metros now drive price appreciation alongside large metros.

**Correlation matrix highlights (2024).**

| Pair | Correlation | Reading |
| --- | --- | --- |
| HPI vs median_income | 0.53 | Income is the strongest non-trivial predictor. |
| HPI vs median_home_value | 0.71 | Strong, expected. |
| HPI vs homeownership_rate | 0.01 | No signal. Ownership rate alone does not predict. |
| HPI vs total_pop | 0.23 | Decoupled from prior. |
| income vs median_home_value | 0.81 | Wealthy metros consistently have expensive housing. |
| age vs homeownership | 0.69 | Life-cycle effect. No HPI signal. |

The income-vs-HPI scatter shows a cluster at HPI 550 to 615 sitting at middle income ($80k-$95k). Those are the migration-driven outliers (Bozeman, Charleston, Naples, Bend) where prices outran local income between 2019 and 2024.

---

## Future Work

| Thread | Why it matters |
| --- | --- |
| Metropolitan-division crosswalk | Recover 37 unmatched FHFA metros, including Chicago, NYC, LA sub-markets. |
| Feature engineering | HPI growth rate, income-to-price ratio, education share, demographic deltas. |
| Baseline regression | Linear + gradient-boosted models. R² establishes the floor. |
| PyTorch VAE for scenarios | Generate synthetic metro-year observations under counterfactual conditions. |
| FAIR metadata | Publish DCAT or Schema.org Dataset metadata. Zenodo deposit with DOI. |

This work continues post-course in `Portfolio/project-big-shoulders/`, a separate repository that reads this project's `hpi_census_merged.csv` as input.

```
THIS REPO    (complete for IS477 scope)
   |         Produces: data/integrated/hpi_census_merged.csv
   |         1,101 rows x 19 cols, 373 metros, 3 years
   |   read-only handoff
   v
Portfolio/project-big-shoulders    ML, scenarios, dashboard (post-course)
                                   Reads merged.csv as input
```

The handoff goes one direction. The post-course repo never edits this project's outputs.

---

## Challenges

**The CBSA type mismatch.** FHFA stored CBSA codes as strings. Census returned them as integers. The initial merge produced zero rows. I diagnosed this as a data unavailability problem until profiling both sides showed identical numeric values stored under different types. Fix: one line. Lesson: profile both sides of any join before merging.

**The 2010 ACS API failure.** The original plan included a 2010 vintage as a Great Recession baseline. The 2010 endpoint returned errors for the variable set that worked for 2015 and later. Variable codes and geographies in the ACS API changed pre-2012. I dropped 2010 and shifted to non-overlapping windows of 2014, 2019, 2024, which is also statistically cleaner. The error handler in `download_census.py` now reports exception type, endpoint, and variables on any vintage failure.

**HPI type/flavor duplication.** Caught during methodology audit, not initial development. The original `groupby` included `hpi_type` and `hpi_flavor` in the keys, preserving multiple HPI variants into the annual aggregation. Each Census row then duplicated across variants on the merge. Pre-fix: 3.77 rows per metro. Post-fix: 2.95. Lesson: an inner join can silently inflate row counts when one side has duplicated keys. A `rows / unique_entities` check catches it.

---

## Reproducing

Set up the environment first.

```bash
cd CourseProjects/IS477-SP26
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Three options to run the pipeline. All produce the same outputs.

**Option A: Snakemake (recommended).**

```bash
snakemake --cores 1
```

Snakemake builds a DAG, only re-runs steps whose inputs changed, and is the standard reproducibility tool.

**Option B: Python wrapper.**

```bash
python run_all.py
```

Simple subprocess wrapper. Always runs all three scripts in order. No incremental rebuild.

**Option C: Run each stage manually.**

```bash
python scripts/download_fhfa.py
python scripts/download_census.py
python scripts/eda_integrate.py
```

**Outputs.**

| Path | Contents |
| --- | --- |
| `data/raw/fhfa/` | HPI master + expanded metro file + manifest |
| `data/raw/census/` | 3 ACS vintages + combined CSV + manifest |
| `data/integrated/` | `hpi_census_merged.csv` |
| `results/visualizations/` | 5 PNGs |

**Verifying integrity.** Each manifest contains SHA-256 checksums. Compare your hash against the committed manifest. A match confirms identical data. A mismatch means upstream FHFA or Census updated their files since the original run.

**Dependencies.** Pinned in `requirements.txt`. The 119-package class template is preserved as `requirements-class-template.txt` for reference.

---

## References

### Datasets

1. Federal Housing Finance Agency. *House Price Index Master File*. https://www.fhfa.gov/data/hpi/datasets?tab=master-hpi-data. Retrieved May 2026. Public domain.
2. U.S. Census Bureau. *American Community Survey 5-Year Estimates*. Vintages 2010-2014, 2015-2019, 2020-2024. https://www.census.gov/data/developers/data-sets/acs-5year.html. Retrieved May 2026. Public domain.

### Methodology

3. U.S. Census Bureau. *When to Use 1-year, 3-year, or 5-year Estimates*. https://www.census.gov/programs-surveys/acs/guidance/estimates.html.
4. U.S. Census Bureau. *Comparing ACS Data: Comparison Profiles and Non-Overlapping 5-Year Estimates*. https://www.census.gov/programs-surveys/acs/guidance/comparing-acs-data.html.
5. Office of Management and Budget. (2023). *2023 Standards for Delineating Core Based Statistical Areas (OMB Bulletin 23-01)*. https://www.census.gov/programs-surveys/metro-micro/about/omb-bulletins.html.
6. Federal Housing Finance Agency. *HPI Frequently Asked Questions and Methodology*. https://www.fhfa.gov/data/hpi/hpi-faqs.

### Software

7. McKinney, W., and the pandas development team. *pandas* v2.1+. https://pandas.pydata.org/.
8. Harris, C. R., Millman, K. J., van der Walt, S. J., et al. (2020). Array programming with NumPy. *Nature* 585, 357-362. https://numpy.org/.
9. Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering* 9(3), 90-95. https://matplotlib.org/.
10. Reitz, K., and contributors. *Requests* v2.31+. https://requests.readthedocs.io/.
11. Waskom, M. L. (2021). seaborn: statistical data visualization. *Journal of Open Source Software* 6(60), 3021. https://seaborn.pydata.org/.
12. openpyxl developers. *openpyxl* v3.1+. https://openpyxl.readthedocs.io/.
13. Python Software Foundation. *Python 3.12 Reference Manual*. https://www.python.org/.

### License

Source code: MIT (`LICENSE`). Data: public domain. Integrated dataset offered into the public domain.
