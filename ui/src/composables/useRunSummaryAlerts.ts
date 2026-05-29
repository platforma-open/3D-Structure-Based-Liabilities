import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { computed, ref, watchEffect, type ComputedRef } from "vue";
import { readNumber, type ScoresTableOutput } from "./ptableCell";

/**
 * Run-summary alert source. Reads `*Flag` columns and
 * `confidenceGatedMotifCount` from the scoresTable PTable and computes:
 *
 *   - fraction of clonotypes with ANY red metric flag. Alert fires above 10%.
 *   - fraction of clonotypes with at least one confidence-gated motif.
 *     Alert fires above 25%.
 */
export type RunSummary = {
  total: number;
  redClonotypes: number;
  gatedClonotypes: number;
  redFraction: number;
  gatedFraction: number;
};

const RED = "red";
const FLAG_COL_NAMES = new Set([
  "pl7.app/liabilities/totalCdrLengthFlag",
  "pl7.app/liabilities/pshFlag",
  "pl7.app/liabilities/ppcFlag",
  "pl7.app/liabilities/pncFlag",
  "pl7.app/liabilities/sfvcspFlag",
  "pl7.app/liabilities/cdrh3CompactnessFlag",
]);
const GATED_COL_NAME = "pl7.app/liabilities/confidenceGatedMotifCount";

const RED_FLAG_THRESHOLD = 0.1;
const GATED_THRESHOLD = 0.25;

export function useRunSummaryAlerts(scoresTable: ComputedRef<ScoresTableOutput>) {
  const runSummary = ref<RunSummary | null>(null);

  watchEffect(async () => {
    const tableOutput = scoresTable.value;
    if (!tableOutput?.ok || !tableOutput.value?.fullTableHandle) {
      runSummary.value = null;
      return;
    }
    const handle = tableOutput.value.fullTableHandle;
    const driver = getRawPlatformaInstance().pFrameDriver;
    const shape = await driver.getShape(handle as never);
    if (shape.rows === 0) {
      runSummary.value = null;
      return;
    }

    const spec = await driver.getSpec(handle as never);
    const flagIndices: number[] = [];
    let gatedIndex = -1;
    for (let i = 0; i < spec.length; i++) {
      const name = spec[i]?.spec?.name;
      if (!name) continue;
      if (FLAG_COL_NAMES.has(name)) flagIndices.push(i);
      if (name === GATED_COL_NAME) gatedIndex = i;
    }
    if (flagIndices.length === 0 && gatedIndex === -1) {
      runSummary.value = null;
      return;
    }

    const requestIndices = [...flagIndices, gatedIndex].filter((i) => i >= 0);
    const data = await driver.getData(handle as never, requestIndices, {
      offset: 0,
      length: shape.rows,
    });
    const rowCount = shape.rows;

    // Any-red-flag-per-row. String columns come back as plain arrays, so a
    // tight Array.isArray check stays cheap.
    let redClonotypes = 0;
    for (let row = 0; row < rowCount; row++) {
      for (let k = 0; k < flagIndices.length; k++) {
        const col = data[k];
        const value = Array.isArray(col?.data) ? col.data[row] : undefined;
        if (value === RED) {
          redClonotypes++;
          break;
        }
      }
    }

    // Gated-motif-count > 0. confidenceGatedMotifCount is Long-typed,
    // which means BigInts inside a numeric-indexed wrapper object; readNumber
    // normalises that to a plain number. The gated column rides at the end
    // of `requestIndices` (after all flag indices), so its data slot is at
    // `flagIndices.length`.
    let gatedClonotypes = 0;
    if (gatedIndex !== -1) {
      const gatedCol = data[flagIndices.length];
      for (let row = 0; row < rowCount; row++) {
        if (readNumber(gatedCol, row) > 0) gatedClonotypes++;
      }
    }

    runSummary.value = {
      total: rowCount,
      redClonotypes,
      gatedClonotypes,
      redFraction: redClonotypes / rowCount,
      gatedFraction: gatedClonotypes / rowCount,
    };
  });

  const showRedAlert = computed(() => (runSummary.value?.redFraction ?? 0) > RED_FLAG_THRESHOLD);
  const showGatedAlert = computed(() => (runSummary.value?.gatedFraction ?? 0) > GATED_THRESHOLD);

  return { runSummary, showRedAlert, showGatedAlert };
}
