/**
 * Helpers for reading values out of `pFrameDriver.getData()` results.
 *
 * The driver returns column-major data where each column's `.data` field
 * is one of:
 *   • a TypedArray (Float64Array, Int32Array, ...)
 *   • a plain Array (e.g. strings)
 *   • a numeric-indexed wrapper object that carries BigInts for Long
 *     columns: `{ 0: 12n, 1: 35n, ... }`
 *
 * Both shape-A (Array.isArray) and shape-C (numeric-indexed object) need
 * different access patterns, and Long values from shape-C are BigInts
 * that JS comparison operators trip over. These helpers normalize to a
 * single `number | string | null` so call sites stay readable.
 */

export type PTableColumn = { data?: unknown } | undefined;

/** Read row `i` from a column as a `string | number`, returning null on
 *  missing / out-of-range. Long BigInts come through as `number`. */
export function readCell(col: PTableColumn, i: number): string | number | null {
  const d = col?.data as unknown;
  if (Array.isArray(d)) {
    const v = (d as unknown[])[i];
    return v === undefined || v === null ? null : (v as string | number);
  }
  if (d && typeof d === "object") {
    const v = (d as Record<string, unknown>)[String(i)];
    return v === undefined || v === null ? null : (v as string | number);
  }
  return null;
}

/** Read row `i` as a number. Treats null / undefined as 0. */
export function readNumber(col: PTableColumn, i: number): number {
  const v = readCell(col, i);
  if (v === null) return 0;
  return Number(v);
}

/** Read row `i` as a number, preserving null for missing cells. Use when
 *  callers need to distinguish "no value" from "0.0". */
export function readNullableNumber(col: PTableColumn, i: number): number | null {
  const v = readCell(col, i);
  return v === null ? null : Number(v);
}

/** Shape of the `scoresTable` output as seen from a Vue composable: a wrapped
 *  `outputWithStatus` result whose `value` carries the two driver handles.
 *  `fullTableHandle` is for pFrameDriver scans (useClusterAssignments,
 *  useRunSummaryAlerts); `fullPframeHandle` is for the SDK column lookups
 *  used by useClonotypeLabels. */
export type ScoresTableOutput =
  | { ok?: boolean; value?: { fullTableHandle?: unknown; fullPframeHandle?: unknown } }
  | undefined;

/** Pull `fullPframeHandle` out of a `scoresTable` output, returning
 *  `undefined` until the output is ready. Used by composables that go
 *  through `getColumnsFull` / `getSingleColumnData` rather than the
 *  pFrameDriver. Typed as `unknown` here because the actual `PFrameHandle`
 *  brand lives in the SDK; callers narrow it at the use site. */
export function pfHandleFrom(out: ScoresTableOutput): unknown {
  return out?.ok && out.value ? out.value.fullPframeHandle : undefined;
}
