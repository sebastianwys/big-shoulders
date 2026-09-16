# ml

Forecasting on top of the pipeline in the repo root. Given what is known about a metro at a quarter, how much does its house price index move over the next one, two, four and eight quarters, and how sure can the model be.

Headline: a sequence GRU cuts the no-change error 39 percent at four quarters and 45 percent at eight, and its bands run 22 to 28 percent narrower than the best classical rule.

## The Input

| item | value |
|---|---|
| file | `../data/integrated/hpi_census_merged.csv` |
| rows x cols | 1,197 x 23 |
| metros | 410, of which 37 are metropolitan divisions |
| years | 2014, 2019, 2024 |
| sha256 | `f0fbb9184aef2e5ca4318b0ccd7aac3431e590701cb6bbc6dc256deac71822e7` |

Read only. This folder never writes to `data/`. If the pipeline re-runs, the hash in the loader is updated in the same commit.

## The Setup

```bash
cd ml
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e .
.venv/bin/python run_tests.py
```

Run the whole chain from the repo root:

```bash
ml/.venv/bin/python -m loop.panel
ml/.venv/bin/python -m loop.baselines
ml/.venv/bin/python -m loop.train
ml/.venv/bin/python -m loop.export
ml/.venv/bin/python -m bot.build_map_data
```

About four minutes on an M4. Every step leaves a figure in `results/figures/`.

## The Panel

One row per metro per quarter. 410 metros, 1975Q1 to 2026Q2, 71,072 rows. FHFA all-transactions gives the target.

Nothing leaks. A monthly value is known in its month. An annual value for year Y is known only from the first quarter of Y+1. Divisions inherit what they lack from the parent metro. `results/panel_manifest.json` records row counts, the non-null share of every column and the parquet hash.

![where the panel has data](results/figures/01_coverage.png)

Prices go back fifty years. Unemployment starts 2014, Zillow values 2000, rents 2015. Covariates arrive late, so the network carries a presence mask per feature.

![house prices since 1990](results/figures/02_hpi_history.png)
![feature trends](results/figures/03_feature_trends.png)
![latest snapshot](results/figures/04_latest_snapshot.png)

## The Evaluation Design

This is the part that makes the numbers mean anything.

The target is log growth of the index over h quarters. A sample is one metro, one origin quarter, one horizon. It lands in a block by where its outcome falls:

| block | outcome realized | used for |
|---|---|---|
| train | by 2017Q4 | fitting |
| calibration | 2018 to 2021 | band width only |
| test | origin 2022Q1 or later | scored once |

Origins whose outcome straddles two blocks are dropped. Nothing realized after 2021 reaches a model judged on 2022 onward.

![how the backtest is split](results/figures/05_backtest_design.png)

Bands come from conformalized quantile regression. The model predicts the 10th, 50th and 90th percentiles. The calibration block sets the smallest widening of that band covering at least 90 percent of held-out outcomes, with the finite sample correction of Romano, Patterson and Candes (2019).

That guarantee assumes exchangeable samples. Quarters are not exchangeable. So the test block coverage is the honest number, and it is reported beside every model.

## The Models

Five classical rules set the bar: no change, momentum, the metro's own average growth, ridge on price lags and covariates, and gradient boosting with quantile losses.

![baseline errors](results/figures/06_baseline_errors.png)
![calibration of the baselines](results/figures/07_calibration.png)
![actual against predicted](results/figures/08_actual_vs_predicted.png)

Two networks share one input: 24 quarters of eight series with a presence mask each, four annual features at the origin, and a learned embedding per metro. The window MLP flattens it into a three layer perceptron. The sequence GRU reads it as a sequence, then concatenates the final state with the annual features and the embedding. Both emit three monotone quantiles per horizon and train on pinball loss with Adam, weight decay and early stopping.

Learning rate and weight decay were chosen on validation loss alone, never on test. One extra experiment: adding the metro running mean and the national mean raised validation loss from 0.006546 to 0.006570, so the simpler input set stays.

![training curves](results/figures/09_training_curves.png)
![quantile calibration](results/figures/10_quantile_calibration.png)

## The Results, 2022Q1 to 2026Q2

Mean absolute error of the median forecast, in percentage points of growth. Coverage is the share of outcomes inside the 90 percent band.

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

Three honest readings of that table.

- The GRU beats every rule that uses recent information. It does not beat the metro's own fifty year average, which edges it by 0.2 and 0.8 points at four and eight quarters. 2022 to 2026 was a return to trend after the 2021 boom, and a long mean is a very good guess at a trend.
- The GRU earns its place on the bands. At four quarters its band is 22 percent narrower than the long run average's, for coverage of 0.96 against 1.00. At eight quarters, 28 percent narrower.
- Its median ran high, by 1.6 points at four quarters and 3.8 at eight. A model fitted through 2017 carried the momentum it saw into a cooling market. The conformal margin repairs coverage, not that tilt.

The window MLP is worse than no change beyond one quarter. It is kept as the honest answer to what a plain perceptron does here.

## The Shipped Forecast

The GRU refitted on every outcome realized by 2026Q2, at the epoch count found above. Its band margin is out of sample: a second GRU fitted through 2021, calibrated on 2022 to 2026, and that margin applied to the final quantiles.

![forecast fans](results/figures/11_forecast_fans.png)
![forecast distribution](results/figures/13_forecast_distribution.png)

At the 2026Q2 origin the median four quarter forecast across 410 metros is 4.4 percent (10th to 90th percentile 2.7 to 6.0), positive everywhere. The eight quarter median is 9.6 percent.

| where | metros | four quarter |
|---|---|---|
| highest | El Centro, Muncie, Rockford, Lima, Erie | 7 to 8 percent |
| lowest | Cape Coral, Punta Gorda, Oakland, Brunswick, Sarasota | under 1.1 percent |
| Chicago division | | 6.3 percent, band -2.6 to 16.8 |

Every band is wide. That is the point of publishing one.

`export.py` writes the map's metrics contract to `results/forecast/metrics.csv`: expected growth at four and eight quarters with bands, realized growth over the last four, the five year annualized trend, and the surprise. The map shows them under Forecasts.

## The Limits

- The 2018 to 2021 calibration block carries the boom's dispersion, so bands over-cover at long horizons and under-cover at one quarter. Rolling the calibration forward would tighten them.
- The GRU sees unemployment and rents only from 2014. Every year of new data helps it more than it helps the long run average.
- Listing and inventory exist only as annual means. Keeping their monthly history would give the model the fastest signal in the set.

## The Layout

```
src/loop/      package code. spec.py is the contract every module imports
tests/         unittest suite, run with run_tests.py
results/       manifests, backtest tables, forecasts, figures. tracked
data/ models/  built panel and trained artifacts. gitignored
MILESTONES.md  the build plan
```

## The Roadmap

| wave | adds | status |
|---|---|---|
| forecasting | quarterly panel, backtest, five baselines, two torch models, conformal bands, map export | done |
| 1 baseline | features, ridge/lasso, gradient boosting, residual analysis | in progress |
| 2 scenarios | conditional sampling, then a small VAE if it earns its place | planned |
| 3 dashboard | streamlit app, public link | planned |
