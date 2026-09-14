import sample from "../fixtures/sample.json";
import type { MapData } from "../types";

export const SAMPLE = sample as unknown as MapData;

// the built json is optional in dev. when it is missing the sample keeps the
// app usable and the header says so
export async function loadMapData(): Promise<{ data: MapData; sample: boolean }> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}data/metros.json`);
    if (!response.ok) throw new Error(String(response.status));
    const data = (await response.json()) as MapData;
    if (!Array.isArray(data?.metros)) throw new Error("unexpected shape");
    return { data, sample: false };
  } catch {
    return { data: SAMPLE, sample: true };
  }
}
