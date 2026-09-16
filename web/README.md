# Loop map

A static map of 410 metros and metropolitan divisions. Each metro is a dot sized by population or a Census boundary shape, colored by the selected metric. Click one for its detail panel.

Data comes from `public/data/metros.json`, which `bot/build_map_data.py` writes from the pipeline output and the bot's sources. Run the pipeline and the bot before deploying.

```
npm install
npm run dev          local server, falls back to a 3-metro sample if the json is missing
npm run test         vitest, offline
npm run build        typecheck then vite build into dist/
npm run boundaries   rebuild the TopoJSON for the Shapes toggle
```

## The National Strip

Thirteen indicators across the top: consumer prices, core CPI and PCE, producer prices, the fed funds rate and where futures put it a year out, the 30-year mortgage rate, the 10-year Treasury, consumer sentiment, expected inflation, unemployment and retail sales.

Each tile shows the latest value, its twelve month change and a sparkline. Opening one gives the full monthly history and names the provider. The numbers come from the national block of `metros.json`, collected from FRED. Without that block the strip is absent.

## The Metrics

Grouped into House prices, Housing market, Rents and affordability, People and migration, Supply, and Forecasts. The menu lists only metrics the built json actually carries, so a source with no key stays hidden.

The "as of" control is a timeline on a calendar axis from 2014 to the newest date in the data. One tick per period, filled where the metric has values and hollow where it is not published, with the metro count under each. Arrow keys step between filled ticks. Play walks the map start to finish.

Forecasts colors the map by the model's expected HPI growth over the next four and eight quarters, realized growth over the last four quarters and five years annualized, and the surprise, actual minus expected. The detail panel adds the 90 percent band. Numbers come from `ml/results/forecast/metrics.csv`, written by `python -m loop.export`.

A monthly bot run carries the last exported forecast until the model is rerun. So the caption date is the forecast origin, not the run date.

## The Shapes Toggle

Draws each metro as its boundary instead of a dot, from `public/data/boundaries.json`. `npm run boundaries` downloads the Census cartographic boundary files and simplifies them with mapshaper, installed one-off with `npm install --no-save mapshaper@0.7` rather than kept as a dependency. The zips stay in `data/raw/boundaries/` with a manifest. The TopoJSON is committed and fetched only when Shapes is first chosen.

## Deploying

Cloudflare Workers flow: Workers and Pages, Create, import the repository.

| setting | value |
|---|---|
| root directory | `web` |
| build command | `npm ci && npm run build` |
| deploy command | `npx wrangler deploy` |
| environment variables | none |

`wrangler.jsonc` points the Worker at `dist` as static assets. The older Pages flow works too, same root and build command, output directory `dist`.

Run `npx wrangler deploy` from `web`, never from the repo root. A root run publishes the whole repo folder as a new Worker.

Tiles are OpenStreetMap. Attribution is in the map and the footer.
