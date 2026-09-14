# Big Shoulders map

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

Cloudflare Pages settings: framework preset Vite, root directory `web`, build
command `npm ci && npm run build`, output directory `dist`, no environment
variables. Tiles are OpenStreetMap, attribution is in the map and the footer.
