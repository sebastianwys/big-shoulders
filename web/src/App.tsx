import { useEffect, useMemo, useState } from "react";
import { DetailPanel } from "./components/DetailPanel";
import { Header } from "./components/Header";
import { Legend } from "./components/Legend";
import { MapView } from "./components/MapView";
import { Sidebar } from "./components/Sidebar";
import { loadMapData } from "./lib/data";
import { METRICS, metricById } from "./lib/metrics";
import { buildScale } from "./lib/scale";
import type { MapData } from "./types";

interface Loaded {
  data: MapData;
  sample: boolean;
}

export function App() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [metricId, setMetricId] = useState(METRICS[0].id);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    loadMapData().then(setLoaded);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelected(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const metric = metricById(metricId);
  const metros = loaded?.data.metros ?? [];
  const scale = useMemo(() => buildScale(metros.map(metric.accessor), metric.kind), [metros, metric]);
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
          metric={metric}
          scale={scale}
          selectedCbsa={selected}
          sources={loaded.data.sources}
          generatedAt={loaded.data.generated_at}
          onMetricChange={setMetricId}
          onSelect={setSelected}
        />
        <div className="map">
          <MapView metros={metros} metric={metric} scale={scale} selectedCbsa={selected} onSelect={setSelected} />
          <Legend scale={scale} metric={metric} />
          {selectedMetro && <DetailPanel metro={selectedMetro} onClose={() => setSelected(null)} />}
        </div>
      </div>
    </div>
  );
}
