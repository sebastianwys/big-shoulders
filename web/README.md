# The Loop map

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

The Shapes toggle draws each metro as its boundary instead of a dot, from
`public/data/boundaries.json`, a TopoJSON that `npm run boundaries` builds by
downloading the Census cartographic boundary files for metros and metropolitan
divisions and simplifying them with mapshaper, a one-off tool installed for that run with `npm install --no-save mapshaper@0.7` rather than kept as a dependency. The zips stay in
`data/raw/boundaries/` with a manifest; the TopoJSON is committed and fetched
only when Shapes is first chosen.

The metric menu is grouped (House prices, Housing market, Rents and
affordability, People and migration, Supply) and only lists metrics the built
json actually carries, so a source without a key yet stays hidden. The "as of"
control picks the panel a metric is read at: 2014, 2019, 2024 or the source's
latest month or year, with periods the metric lacks disabled and change figures
like HPI growth having none. The legend caption names the source and date.

Cloudflare, Workers flow (Workers and Pages, Create, import the repository):
root directory `web`, build command `npm ci && npm run build`, deploy command
`npx wrangler deploy`, no environment variables. `wrangler.jsonc` points the
Worker at `dist` as static assets. The older Pages flow works too: same root
and build command, output directory `dist`. Tiles are OpenStreetMap,
attribution is in the map and the footer.
