// chart tokens. hexes are the documented chart palette, light mode only.
// the sequential ramp is blue steps 250, 350, 450, 550, 700, which pass the
// ordinal ramp validator (light end 2.06:1 on the surface). the diverging red
// arm was computed in oklab to mirror the blue arm's lightness at the palette
// red hue, around the neutral midpoint
export const SURFACE = "#fcfcfb";
export const INK = "#0b0b0b";
export const INK_2 = "#52514e";
export const MUTED = "#898781";
export const ACCENT = "#2a78d6";
export const NULL_GRAY = "#c3c2b7";
export const SEQUENTIAL = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#0d366b"];
export const DIVERGING = ["#1c5cab", "#6da7ec", "#f0efec", "#e4857e", "#9e3432"];
