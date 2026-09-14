Sebastian Wysocki
University of Illinois Urbana-Champaign
IS477 - Data Management, Curation & Reproducibility
March 8th, 2026

# Project Proposal - Housing Affordability Trend Analysis

## The Overview:

This project examines the relationship between the housing price appreciation and the socioeconomic characteristics across U.S. metropolitan areas. The core idea here is straightforward, home price do not move in isolation, neither do they move perfectly with this market. They respond to shifts in income, population growth, dangers from climate change, as well as the demographic makeup of the communities around them, redlining is still embedded in housing prices, even though the practice has been outlawed. By integrating federal housing price data with census-derived demographic and economic indicators, this project builds an end-to-end data pipeline that acquires, cleans, integrates, and analyzes the two government datasets. The first dataset is the FHFA House Price Index, a publicly available index published by the Federal Housing Finance Agency that tracks single-family home value changes at the national, state, and metro area levels. The second is the American Community Survey from the U.S. Census Bureau, which provides demographic, income, and housing data at comparable geographic levels. These two sources use different access methods, carry different data structures, and require integration work to link on geographic identifiers like CBSA and FIPS codes, as seen in the EDA of this project. The project is built to address the course point of reproducibility. Every step from acquisition through analysis is scripted in Python, dependency-managed, and documented so that someone else can clone the repository and replicate this workflow.

## The Team:

Sebastian Wysocki: Working individually, approved. I'm responsible for all aspects of the project including data acquisition, integration, quality assessment, cleaning, analysis, visualization, and to complete documentation from start to finish.

## The Research Questions:

- How does housing price appreciation vary across metropolitan areas with different median household income levels and income growth trajectories?
- Which demographic factors are the strongest predictors of metro-level housing price changes since COVID-19 and since the Great Recession?
- Are there identifiable clusters of metropolitan areas where housing prices have diverged significantly from what income and demographic trends would suggest, what characterizes these outlier markets? (E.g Seattle, Tech Industry (Outlier))

## The Datasets:

FHFA House Price Index (HPI): The dataset measures changes in single-family home values using a weighted repeat-sales methodology applied to mortgage transaction data from Fannie Mae & Freddie Mac. The best part of having access to this dataset is the fact that it has true view into the housing market, not only do we have access to Fannie & Freddie data, we have access to data from VA loans and FHA loans, allowing us to fully capture the population and collect insights. It is available as a direct CSV download from fhfa.gov. As a U.S. government work product, falls under public domain with no license restrictions on redistribution or derivative use.

- The Source: https://www.fhfa.gov/data/hpi/datasets?tab=master-hpi-data
- The Method of Access: Direct CSV download from FHFA
- The License: Public domain (U.S. government mandates full open-source)
- The Format: CSV

American Community Survey (ACS): What needs to be understood is that the ACS is a survey conducted by the U.S. Census Bureau. This survey is done in various time formats but what needs to be understood is that the 5-year estimates offer by far the most reliable data for smaller geographies including metro areas, counties, and census trackers, which is why I'll be embedding the 5-year survey. The data is accessed through the Census Bureau REST API, which return JSON responses for requested data. Census data is public domain and is once again falls under public domain with no license restrictions on redistribution or derivative use.

- The Source: https://www.census.gov/data/developers/data-sets/acs-5year.html
- The Method of Access: REST API, done through the census.gov website
- The License: Public domain (U.S. government mandates full open-source)
- The Format: JSON via API

Just to note that no Kaggle datasets are used in this project, this is due to guidance which was provided as well as licensing issues which I noticed in Kaggle over the years, hard to reproduce

## The Timeline

Period 1 (Estimating March 8-15): Finalize project plan, set up repo, build FHFA and Census ACS acquisition scripts, submit project-plan release when the due date will be released

Period 2 (Estimating March 15-30): Profile datasets through EDA, design storage strategy, integrate on CBSA/FIPS codes, understand and document the schema, take notes for report

Period 3 (Estimating April 1-12): Assess data quality across raw & integrated datasets, clean missing values, outliers, & alignment issues

Period 4 (Estimating April 12-19): Run analysis & build visualizations, automate and document end-to-end workflow, then submit status report and release tag

Period 5 (Estimating April 19-TBA): Write final report in README.md, add metadata documentation, verify reproducibility, submit final-project release

## The Possible Constraints

The FHFA dataset uses a repeat-sales methodology that captures properties with 2+ transactions, which makes me question if I'll run into survivorship bias or possibly underrepresent new construction markets. The Census ACS estimates data over a five-year collection window, which can mask rapid demographic shifts in fast-changing metro areas but as I said, still the best dataset for the task at hand. Geographic alignment requires matching on CBSA codes, and not all FHFA metro area definitions map cleanly to census-defined geographies. Both datasets carry temporal lag as well, which cannot be filtered or ignored. From a licensing standpoint, both datasets are public domain U.S. government works with no redistribution restrictions, which allows the integrated dataset and derived outputs to be shared and reproduced within my GitHub repo.

## The Possible Gaps

I have not yet finalized which ACS variables to pull through the API. The variable selection will depend on profiling of what is available across the metro areas that overlap with the FHFA HPI coverage. I also need to determine whether to use the census API key-based authentication or the key-free access tier. I expect the project plan will evolve as I work through the data integration step and encounter integration issues between the two geographic code styles.
