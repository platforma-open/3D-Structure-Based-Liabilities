/**
 * Inline-style helpers shared across PDB visualization components.
 * Co-located here so visual conventions (overlay-bar geometry, sparkline
 * sizing) stay consistent across the report.
 */

import type { CSSProperties } from "vue";

export const barCellStyle: CSSProperties = {
  position: "relative",
  padding: 0,
  height: "24px",
};

export const barTextStyle: CSSProperties = {
  position: "relative",
  zIndex: 1,
  padding: "0 8px",
};

/** Returns the inline style for a bar that fills `width` % of its parent cell. */
export const bar = (width: string, color: string): CSSProperties => ({
  position: "absolute",
  left: 0,
  top: "4px",
  bottom: "4px",
  width,
  background: color,
  borderRadius: "2px",
});

export const pct = (n: number, max: number): string => `${(n / max) * 100}%`;
export const fmt = (n: number, d = 2): string => n.toFixed(d);
