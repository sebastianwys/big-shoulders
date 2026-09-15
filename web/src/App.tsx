import { useEffect, useMemo, useState } from "react";
import { DetailPanel } from "./components/DetailPanel";
import { Header } from "./components/Header";
import { Legend } from "./components/Legend";
import { MapView } from "./components/MapView";
import { Sidebar } from "./components/Sidebar";
import { loadBoundaries, type BoundaryIndex, type MapMode } from "./lib/boundaries";
import { loadMapData } from "./lib/data";
import { DEFS, availablePeriods, defById, metricCaption, nearestPeriod, resolveMetric, visibleDefs } from "./lib/metrics";
import { buildScale } from "./lib/scale";
import type { MapData, Period } from "./types";

interface Loaded {
  data: MapData;
  sample: boolean;
}

export type ShapesStatus = "idle" | "loading" | "ready" | "failed";

export function App() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [defId, setDefId] = useState(DEFS[0].id);
  const [period, setPeriod] = useState<Period | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState<MapMode>("dots");
  const [boundaries, setBoundaries] = useState<BoundaryIndex | null>(null);
  const [shapesStatus, setShapesStatus] = useState<ShapesStatus>("idle");

  useEffect(() => {
    loadMapData().then(setLoaded);
  }, []);

  // the boundary file is fetched once, the first time shapes are chosen
  useEffect(() => {
    if (mode !== "shapes" || boundaries || shapesStatus !== "idle") return;
    setShapesStatus("loading");
    loadBoundaries().then((index) => {
      if (index) {
        setBoundaries(index);
        setShapesStatus("ready");
      } else {
        setShapesStatus("failed");
      }
    });
  }, [mode, boundaries, shapesStatus]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const metros = loaded?.data.metros ?? [];
  const def = (defById(defId) ?? { def: DEFS[0] }).def;
  const defs = useMemo(() => visibleDefs(metros), [metros]);
  const available = useMemo(() => availablePeriods(def, metros), [def, metros]);
  // a metric that lacks the chosen period moves to the closest one it has
  const activePeriod = nearestPeriod(period, available);
  const metric = useMemo(() => resolveMetric(def, activePeriod), [def, activePeriod]);
  const scale = useMemo(() => buildScale(metros.map(metric.accessor), metric.kind), [metros, metric]);
  const caption = useMemo(() => metricCaption(metric, metros), [metric, metros]);
  const selectedMetro = metros.find((m) => m.cbsa === selected) ?? null;

  if (!loaded) {
    return (
      <div className="app">
        <Header rate={null} sample={false} />
        <p style={{ padding: 16 }}>loading</p>
      </div>
    );
  }

  return (
    <div className="app">
      <Header rate={loaded.data.national?.mortgage_rate ?? null} sample={loaded.sample} />
      <div className="main">
        <Sidebar
          metros={metros}
          defs={defs}
          metric={metric}
          period={activePeriod}
          available={available}
          scale={scale}
          selectedCbsa={selected}
          sources={loaded.data.sources}
          generatedAt={loaded.data.generated_at}
          onMetricChange={setDefId}
          onPeriodChange={setPeriod}
          onSelect={setSelected}
          mode={mode}
          shapesStatus={shapesStatus}
          onModeChange={setMode}
        />
        <div className="map">
          <MapView
            metros={metros}
            metric={metric}
            scale={scale}
            selectedCbsa={selected}
            onSelect={setSelected}
            mode={mode}
            boundaries={boundaries}
          />
          <Legend scale={scale} metric={metric} caption={caption} />
          {selectedMetro && <DetailPanel metro={selectedMetro} onClose={() => setSelected(null)} />}
        </div>
      </div>
    </div>
  );
}
