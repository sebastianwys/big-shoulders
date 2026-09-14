# ml

Modeling on top of the pipeline in the repo root. The pipeline is complete for the IS477 scope and tagged `final-project`. This folder asks what the data can predict.

## Questions

1. Which 2014 to 2019 demographic changes predict 2019 to 2024 price appreciation?
2. Which metros diverged from what demographics would suggest, and by how much?
3. What does a metro look like under a counterfactual (income up, population flat)?

## Input

| item | value |
|---|---|
| file | `../data/integrated/hpi_census_merged.csv` |
| rows x cols | 1,101 x 19 |
| metros | 373 |
| years | 2014, 2019, 2024 |
| sha256 | `c3d1629e4de65f350c8b7fb2c0d82455fd57fbc012a16a3b33cac53b2f014889` |

Read only. This folder never writes to `data/`. If the pipeline re-runs, its scripts rewrite the file and the hash in the loader is updated in the same commit.

## Setup

```bash
cd ml
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/python run_tests.py
```

## Layout

```
src/big_shoulders/   package code
tests/               unittest suite, run with run_tests.py
notebooks/           exploration
models/              trained artifacts (gitignored)
results/             metrics and charts, tracked
MILESTONES.md        the build plan, one commit per milestone
```

## Roadmap

| wave | adds | status |
|---|---|---|
| 1 baseline | features, ridge/lasso, gradient boosting, residual analysis | in progress |
| 2 scenarios | conditional sampling, then a small VAE if it earns its place | planned |
| 3 dashboard | streamlit app, public link | planned |

Each wave ends in a tagged release.
