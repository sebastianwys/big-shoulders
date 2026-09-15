import type { Metro } from "../types";
import { labelFor } from "./metrics";

// one line under a metro name: what a division belongs to, and where its
// zillow values come from. null when there is nothing to say
export function geoNote(metro: Metro): string | null {
  const parts: string[] = [];
  if (metro.level === "division" && metro.parent) {
    parts.push(`Metropolitan division of ${metro.parent.name}`);
  }
  if (metro.zillow_scope === "parent metro") {
    parts.push("Zillow values are for the parent metro");
  }
  return parts.length ? parts.join(". ") + "." : null;
}

// the enrichment metrics a division took from its parent, by their labels
export function parentMetricsNote(metro: Metro): string | null {
  const keys = metro.parent_metrics ?? [];
  if (keys.length === 0) return null;
  const labels = Array.from(new Set(keys.map(labelFor)));
  return `From the parent metro: ${labels.join(", ")}.`;
}
