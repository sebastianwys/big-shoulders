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
| rows x cols | 1,197 x 23 |
| metros | 410, of which 37 are metropolitan divisions |
| years | 2014, 2019, 2024 |
| sha256 | `f0fbb9184aef2e5ca4318b0ccd7aac3431e590701cb6bbc6dc256deac71822e7` |

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
src/loop/        package code
tests/               unittest suite, run with run_tests.py
notebooks/           exploration
data/                the built panel and backtest predictions (gitignored)
models/              trained artifacts (gitignored)
results/             manifests, backtest tables, forecasts and figures, tracked
MILESTONES.md        the build plan, one commit per milestone
```

## Forecasting

The forecasting build asks a different question from the three above: given
everything known about a metro at a quarter, how much will its house price
index move over the next one, two, four and eight quarters, and how sure can
the model be. It is built in steps, and every step leaves a figure in
`results/figures/`. The code is in `src/loop/`: `spec.py` holds the
contract (horizons, quantiles, time blocks, the target, the error measures),
`panel.py` builds the data, `backtest.py` and `baselines.py` run the
classical rules, `nets.py` and `train.py` hold the PyTorch models, and
`export.py` writes the numbers the map reads.

Run the whole chain from the repository root with the ml venv:

```bash
ml/.venv/bin/python -m loop.panel
ml/.venv/bin/python -m loop.baselines
ml/.venv/bin/python -m loop.train
ml/.venv/bin/python -m loop.export
ml/.venv/bin/python -m bot.build_map_data
```

### Step 1, the panel

One row per metro per quarter, 410 metros from 1975Q1 to 2026Q2, 71,072
rows. The house price index comes from the FHFA all-transactions series and
gives the target. The other sources are aligned onto quarters without
leaking the future: a monthly value is known in its month, an annual value
for year Y is only known from the first quarter of Y+1. Metropolitan
divisions inherit what they lack from the parent metro, as the map does. The
manifest in `results/panel_manifest.json` records the row counts, the
non-null share of every column and the parquet hash.

![where the panel has data](results/figures/01_coverage.png)

Prices go back fifty years, unemployment to 2014, Zillow values to 2000 and
rents to 2015, permits, population, income, listings and inventory to the
mid 2010s. A model that wants the long price history has to cope with
covariates that arrive late, which is why the network carries a presence
mask per feature.

![house prices since 1990](results/figures/02_hpi_history.png)

![feature trends](results/figures/03_feature_trends.png)

![latest snapshot](results/figures/04_latest_snapshot.png)

### Step 2, the evaluation design

The target is log growth of the index over h quarters. A sample is one
metro at one origin quarter for one horizon, and it belongs to a block by
where its outcome lands: train when the outcome is realized by 2017Q4,
calibration when it lands inside 2018 to 2021, test when the origin is
2022Q1 or later. Origins whose outcome would fall between blocks are dropped,
so nothing realized after 2021 reaches a model that is judged on 2022
onward. Models fit on the train block only, the calibration block only sets
the width of the bands, and the test block is scored once.

![how the backtest is split](results/figures/05_backtest_design.png)

Bands come from conformalized quantile regression: the model predicts the
10th, 50th and 90th percentiles, and the calibration block sets the smallest
widening of the 10 to 90 band that covers at least 90 percent of held-out
outcomes, with the finite sample correction of Romano, Patterson and Candes
(2019). That guarantee assumes exchangeable samples, and quarters are not
exchangeable, so the coverage on the test block is the honest number and is
reported next to it.

### Step 3, the classical baselines

Five rules set the bar: no change, momentum (the last year's growth carried
forward), the metro's own average growth to date, ridge regression on price
lags and covariates, and gradient boosting with quantile losses. All five
go through the same calibration and scoring.

![baseline errors](results/figures/06_baseline_errors.png)

![calibration of the baselines](results/figures/07_calibration.png)

![actual against predicted](results/figures/08_actual_vs_predicted.png)

### Step 4, the PyTorch models

Two networks share one input: the last 24 quarters of eight quarterly
series (price growth over one and four quarters, unemployment, the
mortgage rate, Zillow value and rent growth, listing price and inventory
growth) with a presence mask per series, four annual features read at the
origin, and a learned embedding per metro. The window MLP flattens the
window into a three layer perceptron. The sequence GRU reads the window
as a sequence and concatenates its final state with the annual features and
the embedding. Both heads emit three quantiles for each of the four
horizons, made monotone by construction, and train on the pinball loss
with Adam, mini batches, weight decay and early stopping on a validation
set carved out of the train block by time (outcomes from 2015 to 2017).

![training curves](results/figures/09_training_curves.png)

Learning rate and weight decay were chosen on that validation loss alone.
One more experiment was run the same way: adding the metro's running mean
growth and the national mean growth as inputs raised the best validation
loss from 0.006546 to 0.006570, so the simpler input set stays.

![quantile calibration](results/figures/10_quantile_calibration.png)

### Step 5, results on the test block, 2022Q1 to 2026Q2

Mean absolute error of the median forecast in percentage points of growth,
and the share of outcomes inside the 90 percent band after calibration.

| model | 1q | 2q | 4q | 8q | coverage 1q/2q/4q/8q |
|---|---|---|---|---|---|
| no change | 2.24 | 3.14 | 5.19 | 10.45 | 0.88 / 0.96 / 1.00 / 0.99 |
| momentum | 2.15 | 3.03 | 5.44 | 13.72 | 0.75 / 0.84 / 0.86 / 0.71 |
| metro mean | 2.00 | 2.48 | 3.04 | 5.30 | 0.89 / 0.97 / 1.00 / 1.00 |
| ridge | 1.95 | 2.48 | 4.04 | 6.72 | 0.78 / 0.90 / 0.91 / 0.88 |
| gradient boosting | 2.03 | 2.91 | 4.72 | 9.64 | 0.79 / 0.83 / 0.93 / 0.94 |
| window mlp | 2.27 | 3.82 | 6.96 | 12.37 | 0.88 / 0.97 / 0.99 / 0.99 |
| sequence gru | 1.98 | 2.50 | 3.23 | 6.09 | 0.83 / 0.92 / 0.96 / 0.92 |

![model comparison](results/figures/12_model_comparison.png)

Three things to say about this table. The GRU beats every rule that uses
recent information, and it cuts the no change error by 39 percent at four
quarters and 45 percent at eight. The one rule it does not beat is a metro's
own long run average, which edges it by 0.2 and 0.8 points at four and eight
quarters: 2022 to 2026 was a return to trend after the 2021 boom, and a
fifty year mean is a very good guess at a trend. The GRU earns its place on
the bands: at four quarters its band is 22 percent narrower than the long
run average's for a coverage of 0.96 against 1.00, and at eight quarters 28
percent narrower. On this block the GRU's median also ran high, by 1.6
points at four quarters and 3.8 at eight, because a model fitted on
outcomes through 2017 carried the momentum it saw into a cooling market;
the conformal margin repairs the coverage but not that tilt, and the
calibration chart shows both.

The window MLP is worse than no change beyond one quarter and stops after
its first epoch. It is kept as the honest answer to what a plain perceptron
does with this data.

### Step 6, the shipped forecast

The shipped model is the GRU refitted on every outcome realized by 2026Q2
with the epoch count found above. Its band uses a margin that is out of
sample for the most recent era: a second GRU fitted on outcomes through
2021 is calibrated on the 2022 to 2026 block, and that margin is applied to
the final model's quantiles.

![forecast fans](results/figures/11_forecast_fans.png)

![forecast distribution](results/figures/13_forecast_distribution.png)

At the 2026Q2 origin the median four quarter forecast across the 410 metros
is 4.4 percent (10th to 90th percentile 2.7 to 6.0), positive everywhere,
and the eight quarter median is 9.6 percent. The highest expected growth
sits in small Midwest and inland metros (El Centro, Muncie, Rockford, Lima,
Erie, all near 7 to 8 percent), the lowest on the Florida Gulf coast and in
the East Bay (Cape Coral, Punta Gorda, Oakland, Brunswick, Sarasota, under
1.1 percent). The Chicago division reads 6.3 percent with a band from -2.6
to 16.8. Every band is wide; that is the point of publishing one.

`export.py` turns the forecast into the map's metrics contract
(`results/forecast/metrics.csv`): expected growth over four and eight
quarters with their bands, realized growth over the last four quarters, the
five year annualized trend, and the surprise, realized minus expected over
the last four quarters from the backtest. The map shows them under
Forecasts.

### What would move the numbers

The 2018 to 2021 calibration block carries the boom's dispersion, so the
bands over-cover at long horizons and under-cover at one quarter. Rolling
the calibration forward every quarter, or calibrating on the most recent
two years, would tighten them. The GRU sees unemployment and rents only
from 2014, which leaves the fitting set three years of covariate history;
every year of new data helps it more than it helps the long run average.
Listing and inventory series exist only as annual means so far; keeping
their monthly history would give the model the fastest moving signal in
the set.

## Roadmap

| wave | adds | status |
|---|---|---|
| 1 baseline | features, ridge/lasso, gradient boosting, residual analysis | in progress |
| forecasting | quarterly panel, rolling backtest, five baselines, two torch models, conformal bands, map export | done, see above |
| 2 scenarios | conditional sampling, then a small VAE if it earns its place | planned |
| 3 dashboard | streamlit app, public link | planned |

Each wave ends in a tagged release.
