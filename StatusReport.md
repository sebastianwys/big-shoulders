Sebastian Wysocki
University of Illinois Urbana-Champaign
IS477: Data Management, Curation & Reproducibility
April 5th, 2026

# The Status Report - Housing Affordability Trend Analysis

## The Progress Update
Since submitting the project plan, I've completed data acquisition for both datasets, run exploratory analysis on each, and built the integration pipeline that joins them on shared geographic codes. The project has working scripts, downloaded data with integrity checksums, an integrated dataset, and five visualizations that start addressing the research questions. Below is a task-by-task breakdown.

### The Data Acquisition
Both acquisition scripts are functional and produce reproducible outputs with SHA-256 checksums logged in manifest files.
For the FHFA House Price Index, I wrote `scripts/download_fhfa.py` which pulls the master HPI file and the expanded-data metro file directly from fhfa.gov. The master file contains 133,216 rows spanning 1975 to 2026 and covers multiple index types (purchase-only, all-transactions, expanded-data), geographic levels (USA, census division, state, MSA), and both monthly and quarterly frequencies. Download metadata is saved to `data/raw/fhfa/download_manifest.json`.
For the Census ACS, I wrote `scripts/download_census.py` which calls the Census Bureau REST API for 5-year estimates across multiple years. The script pulls eight demographic and economic variables at the metropolitan statistical area level, including median household income, total population, median age, educational attainment counts, housing occupancy and ownership figures, and median home value. Data was successfully retrieved for 2015, 2019, and 2022 (2,806 total rows across 961 CBSAs). Each year is saved individually and also combined into a single file at `data/raw/census/acs_5yr_combined.csv`.

### The EDA and Profiling
The EDA work lives in `scripts/eda_integrate.py`. I filtered the FHFA master file down to MSA-level quarterly data, which gave me 93,203 rows across 410 unique metro areas. Most of the seasonally adjusted values at the MSA level are missing (70,243 nulls in `index_sa`), but the non-seasonally adjusted index (`index_nsa`) has zero nulls, so I'm using that as the primary measure. I aggregated quarterly values to annual averages per metro to align with the Census annual estimates.
On the Census side, all eight variables converted to numeric cleanly with no nulls in the 2022 data. I computed a homeownership rate from the occupied and owner-occupied unit counts.

### The Data Integration
The integration joins FHFA and Census data on CBSA codes. One issue I ran into was that FHFA stores CBSA codes as strings while Census returns them as integers, so the initial merge produced zero overlap. After converting the Census codes to strings, the join found 365 overlapping metro areas out of 410 FHFA MSAs and 961 Census CBSAs. The remaining 45 FHFA metros likely use metropolitan division codes rather than CBSA codes, which is a known geographic definition mismatch I'll clean up in the next phase. The integrated dataset has 1,377 rows covering 365 metros across 3 years and is saved at `data/integrated/hpi_census_merged.csv`.

### The Findings (Embedded In Folder)
Five visualizations are saved in `results/visualizations/`. The correlation matrix shows that median income has a ~0.5 correlation with HPI & a ~0.8 correlation with median home value, which makes sense since higher-income metros tend to have more expensive housing. Population shows a moderate 0.40 correlation with HPI. Homeownership rate is weakly negative against HPI, suggesting that metros with higher price appreciation tend to have lower ownership rates, which could reflect affordability pressure. Median age and homeownership rate are strongly correlated with each other (0.66) but neither has a meaningful relationship with HPI on its own.
The top 15 metros by HPI are dominated by Western markets (E.g Austin, Salt Lake City, Denver, Boise, Portland, Phoenix) which aligns with the post-2015 migration and price boom in those regions.

## The Timeline
Period 1 (March 8th-15th) -- Complete: Set up repo, finalized project plan, submitted project-plan release. 
Period 2 (March 15th-April 5th) -- Complete: Built acquisition scripts for both datasets, ran EDA and profiling, integrated datasets on CBSA codes, generated initial visualizations.
Period 3 (April 6th-12th) -- In Progress: Data quality assessment on the integrated dataset, cleaning operations for missing values and geographic code mismatches, deeper analysis addressing each research question.
Period 4 (April 12th-19th) -- Planned: Build automated end-to-end workflow (run_all.sh or Snakemake), finalize analysis and visualizations, status report submission.
Period 5 (April 19-TBA) -- Plannthed: Write final report in README.md, add metadata documentation (Schema.org/DCAT), verify full reproducibility, submit final-project release.

## The Changes from OG Plan
The original plan included pulling Census ACS data for 2010 to use as a Great Recession baseline. The 2010 ACS 5-year API call failed,  due to differences in the variable codes or API structure for that vintage. I adjusted to use 2015, 2019, and 2022, which still captures pre-COVID vs post-COVID shifts & a decade of demographic change. I may revisit the 2010 pull with adjusted variable codes if time allows, but the current three-year window is sufficient to answer the research questions.
I also originally planned to use the FHFA expanded-data index exclusively, but discovered during EDA that the master file contains all index types together. Rather than downloading separate files, I filter within the script, which simplifies the acquisition step.

## The Challenges
The biggest issue was the CBSA code type mismatch between datasets. FHFA stores them as strings, Census as integers. This caused zero overlap on the initial merge and took some debugging to identify. The fix was a one-line type conversion, but it illustrates why profiling both datasets before integration matters.
The 2010 Census API failure was unexpected. I haven't fully diagnosed whether it's a variable code change or an API structure difference for older vintages, but it didn't block progress since the remaining three years provide enough temporal coverage
Roughly 45 FHFA metro areas didn't match any Census CBSA code. These are likely metropolitan divisions (sub-areas of large metros like Chicago, New York, and Los Angeles that FHFA reports separately). Resolving these will require a crosswalk table from the FHFA technical notes, which I plan to address in the cleaning phase.

## The Contribution Summary
What I did thus far was writing all of the acquisition scripts (`download_fhfa.py`, `download_census.py`), designed & implemented the EDA & integration pipeline (`eda_integrate.py`), produced all five visualizations, resolved the CBSA code mismatch, and documented that step-by-step progress in this report.

## The Repository Artifacts
- `scripts/download_fhfa.py` -- FHFA acquisition with SHA-256 checksums
- `scripts/download_census.py` -- Census ACS API client for multiple years
- `scripts/eda_integrate.py` -- EDA, profiling, & dataset integration
- `data/raw/fhfa/` -- Raw FHFA downloads with manifest
- `data/raw/census/` -- Raw Census downloads with manifest
- `data/integrated/hpi_census_merged.csv` -- Joined the datasets
- `results/visualizations/` -- Five visualization outputs
