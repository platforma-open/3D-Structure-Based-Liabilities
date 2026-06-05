import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { computed, ref, watchEffect, type ComputedRef } from "vue";
import { readNumber, type ScoresTableOutput } from "./ptableCell";

/**
 * Run-summary alert source. Reads `confidenceGatedMotifCount` from the
 * scoresTable PTable and surfaces the fraction of clonotypes with at least
 * one confidence-gated motif. Alert fires above 25%.
 */
export type RunSummary = {
  total: number;
  gatedClonotypes: number;
  gatedFraction: number;
};

const GATED_COL_NAME = "pl7.app/liabilities/confidenceGatedMotifCount";
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
    const gatedIndex = spec.findIndex((c) => c?.spec?.name === GATED_COL_NAME);
    if (gatedIndex === -1) {
      runSummary.value = null;
      return;
    }

    const data = await driver.getData(handle as never, [gatedIndex], {
      offset: 0,
      length: shape.rows,
    });
    const gatedCol = data[0];

    let gatedClonotypes = 0;
    for (let row = 0; row < shape.rows; row++) {
      if (readNumber(gatedCol, row) > 0) gatedClonotypes++;
    }

    runSummary.value = {
      total: shape.rows,
      gatedClonotypes,
      gatedFraction: gatedClonotypes / shape.rows,
    };
  });

  const showGatedAlert = computed(() => (runSummary.value?.gatedFraction ?? 0) > GATED_THRESHOLD);

  return { runSummary, showGatedAlert };
}
