/**
 * Shared utilities for the hand-rolled SVG charts (StripPlot,
 * MetricHistogram). Both render with the same axis style + threshold-line
 * scheme, so the tick-position math and the value formatter live here
 * instead of duplicating between components.
 */

/**
 * "Nice" axis ticks: ~`target` ticks at 1/2/5/10×10ⁿ steps inside [min, max].
 *
 * Standard d3-style algorithm — pick a step size from {1, 2, 5, 10} × 10ⁿ
 * that's closest to (max − min) / target, then walk from the first
 * step-aligned value ≥ min up to max. Falls back gracefully when min===max
 * (caller is expected to pad the domain in that case).
 */
export function niceTicks(min: number, max: number, target: number = 5): number[] {
  if (max <= min) return [min];
  const rawStep = (max - min) / target;
  const pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / pow;
  const niceStep = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * pow;
  const startVal = Math.ceil(min / niceStep) * niceStep;
  const out: number[] = [];
  // Add a tiny epsilon to `max` so a tick that lands exactly on the upper
  // bound isn't dropped to floating-point noise.
  for (let v = startVal; v <= max + niceStep * 0.001; v += niceStep) {
    out.push(Number(v.toFixed(6)));
  }
  return out;
}

/**
 * Integer-count ticks (0 .. m) at 1/2/5/10×10ⁿ-aligned steps. Used by
 * MetricHistogram's Y axis where the count is always a non-negative
 * integer. Guarantees the upper bound `m` is in the result so the top
 * bar's count is always labeled.
 */
export function niceIntegerTicks(maxValue: number, target: number = 4): number[] {
  const rawStep = Math.max(maxValue, 1) / target;
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(rawStep, 1))));
  const norm = rawStep / pow;
  const niceStep = Math.max(
    1,
    Math.ceil((norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * pow),
  );
  const out: number[] = [];
  for (let v = 0; v <= maxValue; v += niceStep) out.push(v);
  if (out[out.length - 1] !== maxValue) out.push(maxValue);
  return out;
}

/**
 * Number formatter for axis tick labels — drops trailing decimals for
 * larger magnitudes so labels stay short. Tuned for the Raybould /
 * Gordon metrics our charts plot (PSH 80–180, PPC 0–4, compactness 0–2).
 */
export function fmtAxisValue(v: number): string {
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(2);
}
