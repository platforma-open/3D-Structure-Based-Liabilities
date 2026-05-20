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

/** Read row `i` as a string. Returns null when missing. */
export function readString(col: PTableColumn, i: number): string | null {
  const v = readCell(col, i);
  if (v === null) return null;
  return String(v);
}
