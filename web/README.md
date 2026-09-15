# Loop map

A static map of the 373 metros in the study. Each marker is one metro, sized by
2024 population and colored by the selected metric. Click a marker or a ranked
row for the three-year detail. Data comes from `public/data/metros.json`, which
`bot/build_map_data.py` writes from the pipeline output and the bot's sources,
so run the pipeline and the bot before deploying.

```
npm install
npm run dev        # local server, falls back to a 3-metro sample if the json is missing
npm run test       # vitest, offline
npm run build      # typecheck then vite build into dist/
```

The white strip at the top carries the national picture: consumer prices, core
CPI and PCE, producer prices, the fed funds rate and where futures put it a year
out, the 30-year mortgage rate, the 10-year Treasury, consumer sentiment,
expected inflation, unemployment and retail sales. Each tile gives the latest
value, its twelve month change and a sparkline, and opens a row with the full
monthly history. The numbers come from the national block of
`public/data/metros.json`, collected from FRED, and the expanded row names the
provider. Without it the strip is absent and the mortgage stat stays.

The Shapes toggle draws each metro as its boundary instead of a dot, from
`public/data/boundaries.json`, a TopoJSON that `npm run boundaries` builds by
downloading the Census cartographic boundary files for metros and metropolitan
divisions and simplifying them with mapshaper, a one-off tool installed for that run with `npm install --no-save mapshaper@0.7` rather than kept as a dependency. The zips stay in
`data/raw/boundaries/` with a manifest; the TopoJSON is committed and fetched
only when Shapes is first chosen.

The metric menu is grouped (House prices, Housing market, Rents and
affordability, People and migration, Supply, Forecasts) and only lists metrics the built
json actually carries, so a source without a key yet stays hidden. The "as of"
control is a timeline on a calendar axis from 2014 to the newest date in the
data, with one tick per period: 2014, 2019, 2024 and latest at the source's own
date, filled where the metric has values and hollow where it is not published,
with the metro count under each. Arrow keys step between the filled ticks, play
walks the map from the first to the last, and change figures like HPI growth
show the years they span instead. The legend caption names the source and date.
The detail panel draws the house price history as a chart with the model's
expected path and band when the json carries an annual series, and its vintage
tables add a trend hint per row and a latest column dated by source.

Forecasts is the last group. It colors the map by the model's expected HPI
growth over the next four and eight quarters, the realized growth over the
last four quarters and the last five years annualized, and the surprise,
actual minus expected, for the four quarters just ended. The detail panel
adds the 90 percent band to each expected growth line. The numbers come from
`ml/results/forecast/metrics.csv`, written by `python -m loop.export`
from the model's forecasts and the panel, which the bot picks up beside the
collected sources. A monthly bot run carries the last exported forecast
until the model is rerun, so the caption date is the forecast origin, not
the run date.

Cloudflare, Workers flow (Workers and Pages, Create, import the repository):
root directory `web`, build command `npm ci && npm run build`, deploy command
`npx wrangler deploy`, no environment variables. `wrangler.jsonc` points the
Worker at `dist` as static assets. The older Pages flow works too: same root
and build command, output directory `dist`. Tiles are OpenStreetMap,
attribution is in the map and the footer.
