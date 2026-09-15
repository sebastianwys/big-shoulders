# Project Loop

Housing affordability trend analysis. I integrate the FHFA House Price Index with U.S. Census ACS demographic and economic indicators across U.S. metropolitan areas.

This started as my IS477 final project at the University of Illinois, Project Loop. The pipeline in the repository root is that project, tagged `final-project`. The modeling work that builds on it lives in `ml/` and is in progress.

## The Contributors

Sebastian Wysocki, working individually. I handled every part: dataset selection, acquisition scripts, exploratory analysis, integration, quality assessment, cleaning, visualizations, and this report. All commits in the Git history are mine.

## The Summary

Home prices respond to local income, demographics, education, and housing supply. The question I am answering is which of those signals actually predict housing price appreciation across U.S. metros, and which metros have broken away from what their fundamentals would suggest.

To answer that, I built an end-to-end pipeline. It pulls two government datasets, profiles them, cleans them, joins them on metropolitan statistical area codes, and produces five visualizations along with a clean integrated CSV.

The two sources are the FHFA House Price Index master file and the Census ACS 5-year estimates. FHFA comes as a direct CSV download from fhfa.gov. Census comes through a REST API at api.census.gov. Both are public domain U.S. government works. Both share CBSA codes that allow a clean join.

For Census, I pull three non-overlapping vintages. Vintage 2014 covers surveys from 2010 to 2014, my post-recession baseline. Vintage 2019 covers 2015 to 2019, the pre-COVID peak. Vintage 2024 covers 2020 to 2024, the post-COVID reality. I switched to non-overlapping windows after auditing my methodology. Census's own Comparison Profile guidance is built around non-overlapping intervals. Overlapping windows would have measured the same respondents twice across vintages.

The integrated dataset has 1,197 rows across 410 metros, 373 metropolitan statistical areas plus 37 metropolitan divisions, and three years. Five visualizations live in `results/visualizations/`. The dataset itself is at `data/integrated/hpi_census_merged.csv`.

The headline finding is a regime shift between the 2019 and 2024 vintages. The earlier top-15 list was dominated by Western tech metros like Austin, Salt Lake City, Denver, Boise, and Phoenix. The 2024 list is led by Bozeman MT, with Charleston SC, Naples FL, San Jose CA, and San Diego CA in the top five. Two Montana metros now appear in the top 15. Mountain towns and Sun Belt coastal markets replaced urban tech centers. That is the visible signature of remote-work migration.

The numerical version of that story is in the correlation matrix. Population correlation with HPI dropped from approximately 0.40 in earlier vintage analysis to 0.23 in the 2024 vintage. Smaller amenity-rich metros now drive price appreciation alongside larger ones. Metro size has become a weaker predictor than it used to be. Median income remains the strongest non-trivial predictor at 0.53 correlation.

The reproducibility infrastructure has SHA-256 checksums for every download, structured manifests with source endpoints and ISO 8601 UTC timestamps, an empty-merge guard, stale-file cleanup, a Snakefile with three rules, and a `run_all.py` Python wrapper. Source code is MIT licensed. The data is public domain.

## The Data Profile

### The Ethical and Legal Notes

Both datasets are U.S. government works in the public domain. The bot's added sources are public domain government data except Zillow Research and Realtor.com Economic Research, which are used under their terms with attribution and whose raw files are not redistributed here. There is no personally identifiable information because both datasets aggregate to the metropolitan statistical area level, which is the smallest geographic unit. ACS responses are mandatory under Title 13 of the U.S. Code. FHFA HPI is computed from mortgage transaction data already aggregated by Fannie Mae, Freddie Mac, FHA, and VA loan portfolios. There are no copyright restrictions because U.S. government works are public domain under 17 USC 105. The MIT license in this repository covers source code only. The data is unrestricted.

### The FHFA House Price Index

The FHFA HPI master file is the U.S. government's official measure of single-family home value changes. It uses a weighted repeat-sales methodology applied to mortgage transaction data from Fannie Mae, Freddie Mac, FHA, and VA loans. The full file has approximately 186,000 rows spanning 1975 to 2026 as of the September 2026 pull. It covers multiple index types, multiple geographic levels, and both monthly and quarterly frequencies.

| Field | Value |
| --- | --- |
| Location | `data/raw/fhfa/hpi_master.csv` |
| Source | https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv |
| Provider | Federal Housing Finance Agency |
| Access | Direct HTTP download |
| License | Public domain |
| Format | CSV, approximately 16.8 MB |
| Manifest | `data/raw/fhfa/download_manifest.json` |
| Vintage | Pulled 2026-09-14. FHFA offers no vintage parameter, see The Challenges. |

After filtering to the canonical inter-metro index (MSA, quarterly, traditional, all-transactions), the working slice is 71,072 rows across 410 unique MSAs.

#### The FHFA Data Dictionary

| Column | Type | Description |
| --- | --- | --- |
| `place_id` | string | CBSA or metropolitan division code. Joins to Census `geo_code`. |
| `place_name` | string | Metro name. |
| `hpi_type` | string | Filtered to `traditional`. |
| `hpi_flavor` | string | Filtered to `all-transactions`. |
| `level` | string | Filtered to `MSA`. |
| `frequency` | string | Filtered to `quarterly`. |
| `yr` | int | Year of observation. |
| `period` | int | Quarter (1 to 4). |
| `index_nsa` | float | Non-seasonally adjusted HPI. The primary measure I use. |
| `index_sa` | float | Seasonally adjusted HPI. 100 percent null at MSA level. Not used. |
| `rstderr` | float | Populated only for the expanded-data series. Not used. |
| `note` | string | Suppression notes for the expanded-data series. Not used. |

### The Census ACS 5-Year Estimates

The American Community Survey is an ongoing survey conducted by the U.S. Census Bureau. The 5-year estimates pool 60 months of survey responses to give statistically reliable estimates at the MSA level. I pull three non-overlapping vintages.

| Vintage | Survey Window | Role | File | Rows |
| --- | --- | --- | --- | --- |
| 2014 | 2010 to 2014 | Post-recession baseline | `acs_5yr_2014.csv` | 929 |
| 2019 | 2015 to 2019 | Pre-COVID peak | `acs_5yr_2019.csv` | 938 |
| 2024 | 2020 to 2024 | Post-COVID reality | `acs_5yr_2024.csv` | 935 |
| Combined | All three | Used in merge | `acs_5yr_combined.csv` | 2,802 |

| Field | Value |
| --- | --- |
| Source endpoint | `https://api.census.gov/data/{year}/acs/acs5` |
| Provider | U.S. Census Bureau |
| Access | REST API (JSON) |
| License | Public domain |
| Geography | All metropolitan and micropolitan statistical areas |
| Manifest | `data/raw/census/download_manifest.json` |

#### The Census Data Dictionary

| Original | Renamed | Type | Description |
| --- | --- | --- | --- |
| `NAME` | `NAME` | string | Metro name. |
| (geo) | `cbsa_code` | string | CBSA code. Cast from int to string for the join. |
| `B19013_001E` | `median_income` | float | Median household income (USD). |
| `B01003_001E` | `total_pop` | float | Total population. |
| `B01002_001E` | `median_age` | float | Median age in years. |
| `B15003_022E` | `bachelors_count` | float | Persons with bachelor's degree. |
| `B15003_023E` | `masters_count` | float | Persons with master's degree. |
| `B25003_001E` | `total_occupied_units` | float | Total occupied housing units. |
| `B25003_002E` | `owner_occupied_units` | float | Owner-occupied housing units. |
| `B25077_001E` | `median_home_value` | float | Median home value (USD). |
| derived | `homeownership_rate` | float | `owner / total`. |
| added | `year` | int | Vintage tag. |

### The Schema

This is how the two datasets connect.

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
                  410 unique metros
                  years: 2014, 2019, 2024
```

### The Storage Strategy

This project uses a tabular data model. Raw and integrated datasets are CSV. JSON manifests track integrity and provenance. PNG files store visualizations. CSV is human-readable, version-controllable, and works directly with pandas. The dataset is small enough that no relational database is needed. Per-source folders keep raw files separated from derived files.

```
loop/
|-- scripts/                     acquisition + integration scripts
|-- data/
|   |-- raw/
|   |   |-- fhfa/                pulled from FHFA + manifest
|   |   |-- census/              pulled from Census API + manifest
|   |   `-- <source>/            one folder per bot source, manifest + metrics.csv
|   `-- integrated/              merged output (final dataset)
|-- results/
|   `-- visualizations/          5 PNG charts
|-- ml/                          modeling work, see ml/MILESTONES.md
|-- bot/                         collectors and the map data build
|-- web/                         react and leaflet map of the metros
|-- tests/                       pipeline and bot tests, python run_tests.py
|-- README.md                    project report
|-- LICENSE                      MIT for code, public domain for data
|-- metadata.jsonld              Schema.org Dataset description
|-- Snakefile                    workflow definition
|-- run_all.py                   simple Python wrapper
`-- requirements.txt             pinned dependencies
```

Naming follows a few simple rules. Raw files keep their source name. Integrated outputs use compound names showing the join. Manifests are always `download_manifest.json` inside each source folder. Visualizations use snake_case descriptive names.

### The Data Lifecycle

This project follows the DCC (Digital Curation Centre) Curation Lifecycle Model. Each phase maps to a specific artifact in the repo.

| DCC Phase | This Project |
| --- | --- |
| Conceptualise | the project plan defined the research questions and dataset selection |
| Create or Receive | `scripts/download_fhfa.py`, `scripts/download_census.py` |
| Appraise and Select | Filter to MSA, quarterly, traditional, all-transactions |
| Ingest | Save to `data/raw/` with SHA-256 manifest |
| Preservation Action | Public domain inputs, MIT license, structured manifests |
| Store | `data/raw/` and `data/integrated/` committed to GitHub |
| Access, Use, Reuse | `README.md`, `Snakefile`, `run_all.py`, `metadata.jsonld` |
| Transform | `scripts/eda_integrate.py` cleans, joins, derives, visualizes |

The pipeline can re-execute when upstream sources update. The SHA-256 mechanism flags when this happens, so downstream stages re-run only when inputs actually changed.

### The Integrated Dataset

| Field | Value |
| --- | --- |
| Location | `data/integrated/hpi_census_merged.csv` |
| Rows | 1,197 |
| Columns | 19 |
| Unique metros | 410 |
| Years | 2014, 2019, 2024 |
| Join | Inner join on (`place_id`, `yr`) and (`cbsa_code`, `year`) |

## The Data Quality

I checked five quality dimensions during integration. Profile output is captured in script logs.

| Dimension | Result | Action Taken |
| --- | --- | --- |
| FHFA completeness | `index_nsa`: 0 nulls. `index_sa`: 100 percent nulls. | Use `index_nsa`. SA index not published at MSA level. |
| Census completeness | Below 1 percent suppressed values per variable. | Coerce sentinel `-666666666` to NaN with `pd.to_numeric`. |
| Type consistency | FHFA stores codes as strings. Census returns ints. Initial merge: 0 overlap. | Cast Census `cbsa_code` to string before join. |
| Geographic coverage | 410 FHFA codes vs 1,010 Census CBSAs plus 37 divisions. Overlap: 410. | FHFA publishes the 13 largest metros only as divisions. ACS is pulled at the division level for those parents and four renamed division codes are crosswalked. |
| Temporal coverage | FHFA 1975 to 2026. Census 3 vintages. | Inner join restricts to vintage years. 1,197 rows of theoretical 1,230 (410 x 3). |

The most consequential issue I found was the CBSA code type mismatch. FHFA stores CBSA codes as strings. The Census API returns them as integers. The first time I ran the merge it produced zero rows. I diagnosed this as a data unavailability problem until profiling both sides showed identical numeric values stored under different types. The fix was a single line, `astype(str)` on the Census side. After that the join recovered the full 373-metro overlap.

The second issue was the FHFA seasonally adjusted index. I noticed `index_sa` had 71,072 nulls out of 71,072 rows at the MSA traditional all-transactions filter. That is 100 percent missing. FHFA does not publish a seasonally adjusted index at that level. I switched to `index_nsa`, which has zero nulls. The script logs this so it is visible on every run.

The third issue was Census suppression. The Census API returns the sentinel string `-666666666` for suppressed values rather than null. Without coercion, those sentinels would survive into the integrated dataset and corrupt every aggregation downstream. I run `pd.to_numeric` with `errors="coerce"` on all eight numeric variables. The post-coerce null rate is below 1 percent per variable.

The fourth issue was geographic coverage. The 37 unmatched FHFA metros were the metropolitan divisions of the 13 largest metros, which FHFA publishes instead of the parent metro. Pulling ACS at the division level for those parents and crosswalking four renamed division codes brought all 410 FHFA codes into the merge. Division rows carry `geo_level` of `division` and their parent code in `parent_cbsa`.

The fifth issue is temporal coverage. Some metros do not have FHFA data for all three vintage years, usually because they are newer MSA designations. Those metros drop from the inner join, which is why my merge size is 1,101 rows out of a theoretical maximum of 1,119.

A `download_manifest.json` for each dataset records filename, source, SHA-256 checksum, file size, row count, vintage, and ISO 8601 UTC timestamp. A re-download with a different hash is the trigger to re-run downstream stages. This catches upstream FHFA monthly updates and Census API revisions automatically.

## The Data Cleaning

I applied five operations across the pipeline. Each addresses a specific quality issue.

The first operation is the FHFA series lock. Before aggregating, I filter to `level == "MSA"`, `frequency == "quarterly"`, `hpi_type == "traditional"`, and `hpi_flavor == "all-transactions"`. Without this lock, multiple HPI variants per metro-year survived into the annual aggregation and duplicated Census rows on the merge. The pre-fix merge was 3.77 rows per metro across three years, mathematically impossible without duplication. The post-fix merge is 2.95 rows per metro, close to the expected 3. Some metros are missing data for one vintage, which is why it sits below the maximum.

The second operation is the quarterly to annual collapse. FHFA has quarterly observations. Census has annual estimates. I aggregate FHFA quarters to annual averages per metro using `groupby(["place_id", "place_name", "hpi_type", "hpi_flavor", "yr"]).agg(avg_index_nsa=("index_nsa", "mean"), quarters_available=("index_nsa", "count"))`. The `quarters_available` column flags incomplete years where fewer than four quarters are present.

The third operation is the Census numeric conversion. The Census REST API returns every field as a string, including numeric variables. I coerce eight variables (`median_income`, `total_pop`, `median_age`, `bachelors_count`, `masters_count`, `total_occupied_units`, `owner_occupied_units`, `median_home_value`) to numeric with `pd.to_numeric(errors="coerce")`. The Census suppression sentinel `-666666666` and any other non-numeric values become NaN.

The fourth operation is the CBSA type cast. Census `cbsa_code` is cast to string with `astype(str)` before the merge to match FHFA's string format. This single line restored the full 373-metro overlap.

The fifth operation is a derived column. I compute `homeownership_rate = owner_occupied_units / total_occupied_units`. A normalized rate is more comparable across metros of different sizes than absolute counts.

The merge itself is an inner join on (`place_id`, `yr`) and (`cbsa_code`, `year`). I added an empty-merge guard that raises `RuntimeError` if the join produces zero rows. That guard catches CBSA boundary changes across vintages before they corrupt downstream stages with an empty CSV.

## The Findings

The 2024 vintage shows a regime shift in metropolitan housing markets compared with the 2022-vintage baseline.

The first finding is the top-15 list inversion. The 2022 top-15 was dominated by Western tech metros like Austin, Salt Lake City, Denver, Boise, and Phoenix. The 2024 top-15 is led by Bozeman MT at HPI 615. The next four are Charleston SC, Naples FL, San Jose CA, and San Diego CA. The full 2024 list rounds out with Bend OR, Barnstable Town MA, Missoula MT, Austin (now mid-rank), Phoenix, Asheville NC, North Port-Bradenton-Sarasota FL, Coeur d'Alene ID, San Luis Obispo CA, and Denver (also mid-rank). Salt Lake City, Boise, and Portland fell off the top 15 entirely. Two Montana metros (Bozeman and Missoula) now appear. Mountain towns and Sun Belt coastal markets replaced the urban tech-driven story.

The second finding is the population-HPI decoupling. Population correlation with HPI dropped from approximately 0.40 in 2022-vintage analysis to 0.23 in the 2024 vintage. Smaller amenity-rich metros now drive price appreciation alongside larger ones. Metro size has become a weaker predictor than it used to be.

The third finding is in the full correlation matrix at the 2024 vintage. Median income vs HPI is 0.53, the strongest non-trivial predictor. Median home value vs HPI is 0.71, expected since HPI measures the appreciation of home values. Income vs median home value is 0.81, meaning wealthy metros consistently have expensive housing. Homeownership rate vs HPI is 0.01, essentially zero. Ownership rate alone does not predict appreciation. Median age vs homeownership is 0.69, which captures the well-documented life-cycle effect of older metros having more owners. None of those age-driven effects translate into HPI on their own.

The income-vs-HPI scatter plot makes the affordability story visible. There is a cluster of metros at HPI 550 to 615 sitting at middle income (80k to 95k median household income). Those are the migration-driven outliers like Bozeman, Charleston, Naples, and Bend, where prices outran local income between 2019 and 2024.

The five visualizations in `results/visualizations/` are the histogram of HPI distribution, the income vs HPI scatter, the homeownership vs HPI scatter, the top-15 bar chart, and the correlation matrix heatmap.

## The Future Work

The modeling work continues in `ml/` in this repository. It reads `data/integrated/hpi_census_merged.csv` as input and never edits it. `ml/MILESTONES.md` is the plan from here.

```
pipeline (repo root, tagged final-project)
   |         produces data/integrated/hpi_census_merged.csv
   |         1,197 rows x 23 cols, 410 metros, 3 years
   |   read-only handoff
   v
ml/        features, baseline models, scenarios, dashboard
```

Five threads continue post-course.

The first thread, the metropolitan-division crosswalk, is done as of 2026-09-15. See the fifth challenge.

The second thread is feature engineering for ML. The current integrated dataset is a foundation, not a feature set. ML-ready features include HPI growth rate (year-over-year change or log-difference between vintages), income-to-price ratio (`median_home_value / median_income`), education share (`(bachelors_count + masters_count) / total_pop`), and demographic deltas across the three vintages.

The third thread is a baseline regression model. A scikit-learn linear regression and a gradient-boosted regression on those features, predicting 2024 HPI from 2014 and 2019 demographics, would establish a baseline. The R-squared and feature importance from that baseline would tell me which Census variables to add in subsequent pulls and which features actually drive the regime change between 2019 and 2024.

The fourth thread is generative scenarios. The originally planned PyTorch Variational Autoencoder for housing market scenarios would consume the same merged dataset and produce synthetic metro-year observations under counterfactual demographic conditions.

The fifth thread is FAIR metadata expansion. The current `metadata.jsonld` is a Schema.org Dataset description tied to this repo. Publishing a DCAT-compliant metadata file or a DataCite descriptor for a Zenodo deposit would make the integrated dataset machine-discoverable and FAIR-compliant for external use.

The biggest lesson from this project is that data curation work is mostly diagnosing silent failures. The merge that returned zero rows looked like a data availability problem until I profiled both datasets and saw the type mismatch. The 3.77-rows-per-metro inflation looked correct on the surface until I sanity-checked it against the expected 3. Both fixes were one line. Both took longer to find than to write. Profiling both sides of any join, and validating row counts against expected entity counts, is what saves you from corrupted analysis downstream.

## The Challenges

Five challenges shaped this project. I want to call them out.

The first challenge was the CBSA code type mismatch. FHFA stores CBSA codes as strings. The Census API returns them as integers. The initial merge produced zero overlapping rows. I diagnosed this as a data unavailability problem until profiling both sides revealed identical numeric values stored under different types. The fix was a single line, `astype(str)` on the Census side. The lesson was that profiling both sides of any join before merging is non-negotiable.

The second challenge was the 2010 ACS API failure. The original plan included a 2010 vintage as a Great Recession baseline. The 2010 endpoint returned errors for the variable set that worked for 2015 and later. Variable codes and geography definitions in the ACS API changed pre-2012. I documented the failure mode, dropped 2010, and shifted to non-overlapping windows of 2014, 2019, 2024. That ended up being statistically cleaner anyway because the Census Comparison Profile methodology is built around non-overlapping intervals. The error handler in `download_census.py` now reports exception type, endpoint, and variables on any vintage failure, so the next failure of this kind is immediately diagnosable.

The third challenge was the HPI type/flavor duplication. I caught this during a methodology audit, not during initial development. My original `groupby` included `hpi_type` and `hpi_flavor` in the keys, which preserved all HPI variants into the annual aggregation. Each Census row then duplicated across variants on the merge. Pre-fix the merge was 3.77 rows per metro across three years. Post-fix it is 2.95. The lesson was that an inner join can silently inflate row counts when one side has duplicated keys, and a `rows / unique_entities` check is a good sanity step.

The fourth challenge was the FHFA vintage problem, found on 2026-09-14 while proving a clean start-to-finish run. The Census half reproduced byte for byte because every ACS endpoint carries its vintage in the URL. The FHFA half did not. `hpi_master.csv` is a live file with no vintage parameter, and between May and September FHFA added two quarters and two columns, expanded one series from 7,000 rows to 58,220, and revised the historical index. My merged dataset kept its 1,101 rows, but 1,094 changed value and its SHA-256 moved from `08c906a7` to `c3d1629e` with no code change. The lesson was that when a source cannot be addressed by vintage, the archived raw file in version control is the vintage. I adopted the September pull in one dedicated commit, so `git log -- data/raw/fhfa/hpi_master.csv` shows both snapshots.

The fifth challenge was the missing big metros. FHFA publishes the 13 largest metropolitan areas only as their metropolitan divisions, so Chicago, New York, Los Angeles and ten others never joined to the Census rows, which are keyed by the parent metro code. A housing study with no Chicago is not much of a housing study. The fix pulls ACS at the division level for those 13 parents, joins on the division code, and crosswalks four division codes that OMB renamed between 2013 and 2023. That raised the join from 373 metros to all 410 FHFA codes.

## The Reproducing Steps

Set up the environment first.

```bash
cd loop
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The Census API requires a key. Request one at https://api.census.gov/data/key_signup.html, click the activation link in the email, and export it. Without it the API returns an HTML page with a 200 status, which `download_census.py` detects.

```bash
export CENSUS_API_KEY=your_key_here
```

Three options to run the pipeline. All produce the same outputs.

Option A is Snakemake, which I recommend.

```bash
snakemake --cores 1
```

Snakemake builds a DAG of three rules and only re-runs steps whose inputs changed.

Option B is the Python wrapper.

```bash
python run_all.py
```

The wrapper runs the same three scripts in order using subprocess. It does not track dependencies.

Option C is to run each script manually in order.

```bash
python scripts/download_fhfa.py
python scripts/download_census.py
python scripts/eda_integrate.py
```

The ACS end years are pinned in `data/raw/census/vintages.json`. A plain run reads the pin. `python scripts/download_census.py --refresh-vintages` re-resolves the newest vintage from the Census catalog and moves the window forward deliberately.

Outputs land in:

| Path | Contents |
| --- | --- |
| `data/raw/fhfa/` | HPI master + expanded metro file + manifest |
| `data/raw/census/` | 3 ACS vintages + combined CSV + manifest |
| `data/integrated/` | `hpi_census_merged.csv` |
| `results/visualizations/` | 5 PNGs |

To verify integrity, compare your computed SHA-256 hashes against the committed manifests. Census files should match, because each ACS vintage endpoint is fixed. FHFA files will not, because `hpi_master.csv` is a live file that FHFA revises every quarter. The committed `data/raw/fhfa/` is the archived snapshot this report describes. To regenerate the committed outputs from it without downloading, run `snakemake --cores 1 --forcerun integrate` and compare the merged file to the hash in `ml/README.md`.

## The Bot and the Map

`bot/` collects the enrichment sources on a monthly GitHub Actions schedule and rebuilds `web/public/data/metros.json`. Each source is one collector in `bot/collectors/` that writes `data/raw/<source>/` with a manifest in the pipeline's shape and a `metrics.csv` the map builder discovers by convention. Sources: Census Gazetteer centroids (metropolitan division centroids derived from their counties), Zillow ZHVI and ZORI plus inventory, days to pending, price cuts and the ZHVF forecast, BLS metro unemployment, the FRED 30-year mortgage rate, thirteen national indicators from FRED for the dashboard strip (prices, rates and consumers, listed in `bot/indicators.py`), six more ACS measures (gross rent, rent burden, vacancy, commute, poverty, labor force), Census population estimates with migration components, Census building permits, Realtor.com listing metrics, IRS county-to-county migration, and, with keys, BEA personal income and HUD fair market rents and income limits. Divisions inherit metro-level sources from their parent and say so. Run it by hand from the root with `python -m bot.run_bot`. Keys: `CENSUS_API_KEY` and `FRED_API_KEY` are required; `BLS_API_KEY`, `BEA_API_KEY` and `HUD_API_TOKEN` unlock the rest, and a source whose key is missing is skipped.

`web/` is a React and Leaflet map of the 410 metros and divisions: dots sized by population or Census boundary shapes, colored by any metric for 2014, 2019, 2024 or the latest reading, with a detail panel per metro. It is static, reads the committed JSON, and deploys to Cloudflare from the `web` directory. Settings are in `web/README.md`.

The map also carries a Forecasts group: expected growth of the house price index over the next four and eight quarters with 90 percent bands, the five year trend and a surprise measure, from a PyTorch sequence model trained on a quarterly panel of every metro since 1975 and judged on a held out 2022 to 2026 block against five classical rules. The build, its evaluation design and every step figure are in `ml/README.md`.

## The References

### Datasets

1. Federal Housing Finance Agency. *House Price Index Master File*. https://www.fhfa.gov/data/hpi/datasets?tab=master-hpi-data. Retrieved September 2026. Public domain.
2. U.S. Census Bureau. *American Community Survey 5-Year Estimates*. Vintages 2010 to 2014, 2015 to 2019, 2020 to 2024. https://www.census.gov/data/developers/data-sets/acs-5year.html. Retrieved May 2026. Public domain.

### Methodology

3. U.S. Census Bureau. *When to Use 1-year, 3-year, or 5-year Estimates*. https://www.census.gov/programs-surveys/acs/guidance/estimates.html.
4. U.S. Census Bureau. *Comparing ACS Data: Comparison Profiles and Non-Overlapping 5-Year Estimates*. https://www.census.gov/programs-surveys/acs/guidance/comparing-acs-data.html.
5. Office of Management and Budget. (2023). *2023 Standards for Delineating Core Based Statistical Areas (OMB Bulletin 23-01)*. https://www.census.gov/programs-surveys/metro-micro/about/omb-bulletins.html.
6. Federal Housing Finance Agency. *HPI Frequently Asked Questions and Methodology*. https://www.fhfa.gov/data/hpi/hpi-faqs.

### Software

7. McKinney, W., and the pandas development team. *pandas* v2.1+. https://pandas.pydata.org/.
8. Harris, C. R., Millman, K. J., van der Walt, S. J., et al. (2020). Array programming with NumPy. *Nature* 585, 357 to 362. https://numpy.org/.
9. Hunter, J. D. (2007). Matplotlib: A 2D graphics environment. *Computing in Science & Engineering* 9(3), 90 to 95. https://matplotlib.org/.
10. Reitz, K., and contributors. *Requests* v2.31+. https://requests.readthedocs.io/.
11. Waskom, M. L. (2021). seaborn: statistical data visualization. *Journal of Open Source Software* 6(60), 3021. https://seaborn.pydata.org/.
12. openpyxl developers. *openpyxl* v3.1+. https://openpyxl.readthedocs.io/.
13. Python Software Foundation. *Python 3.12 Reference Manual*. https://www.python.org/.

### License

Source code: MIT (`LICENSE`). Data: public domain. Integrated dataset offered into the public domain.
