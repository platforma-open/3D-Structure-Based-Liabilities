import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { computed, ref, watchEffect, type ComputedRef, type Ref } from "vue";
import { readCell, readNullableNumber, readNumber, type ScoresTableOutput } from "./ptableCell";

/**
 * Per-clonotype cluster assignment, joined onto scoresTable via the
 * scClonotypeKey axis when the 3D Structure Clustering block sits
 * upstream. When clustering isn't in the pipeline the map stays empty
 * and the slideover hides cluster bits.
 */
export type ClusterAssignment = {
  clusterId: string;
  isCentroid: boolean;
  tmDistanceToCentroid: number | null;
  tmScoreToCentroid: number | null;
};

/**
 * Subscribe to the scoresTable PTable and rebuild a per-clonotype cluster
 * assignment map whenever it changes. `selectedClonotypeKey` is passed
 * in (rather than created inside) so the cluster badge in the slideover
 * stays bound to the row the user opened.
 */
export function useClusterAssignments(
  scoresTable: ComputedRef<ScoresTableOutput>,
  selectedClonotypeKey: Ref<string | null>,
) {
  const clusterMap = ref<Record<string, ClusterAssignment>>({});

  watchEffect(async () => {
    const tableOutput = scoresTable.value;
    if (!tableOutput?.ok || !tableOutput.value?.fullTableHandle) {
      clusterMap.value = {};
      return;
    }
    const handle = tableOutput.value.fullTableHandle;
    const driver = getRawPlatformaInstance().pFrameDriver;
    const shape = await driver.getShape(handle as never);
    if (shape.rows === 0) {
      clusterMap.value = {};
      return;
    }
    const spec = await driver.getSpec(handle as never);

    // Locate the columns we care about by name. Missing columns mean the
    // clustering block isn't in the pipeline → bail with an empty map.
    let keyIdx = -1;
    let clusterIdIdx = -1;
    let isCentroidIdx = -1;
    let tmDistIdx = -1;
    let tmScoreIdx = -1;
    for (let i = 0; i < spec.length; i++) {
      const e = spec[i];
      if (e?.type === "axis" && e.spec?.name === "pl7.app/vdj/scClonotypeKey") keyIdx = i;
      else if (e?.type === "column") {
        const n = e.spec?.name;
        if (n === "pl7.app/clusterId") clusterIdIdx = i;
        else if (n === "pl7.app/structure/clustering/isCentroid") isCentroidIdx = i;
        else if (n === "pl7.app/structure/clustering/tmDistanceToCentroid") tmDistIdx = i;
        else if (n === "pl7.app/structure/clustering/tmScoreToCentroid") tmScoreIdx = i;
      }
    }
    if (keyIdx === -1 || clusterIdIdx === -1) {
      clusterMap.value = {};
      return;
    }

    // Request only the columns that actually exist; the pf driver returns
    // them in the order we ask for. `posOf` translates the original spec
    // index back into the position in the returned data array.
    const indices = [keyIdx, clusterIdIdx, isCentroidIdx, tmDistIdx, tmScoreIdx].filter(
      (i) => i >= 0,
    );
    const data = await driver.getData(handle as never, indices, {
      offset: 0,
      length: shape.rows,
    });
    const posOf = (idx: number) => indices.indexOf(idx);

    const out: Record<string, ClusterAssignment> = {};
    for (let row = 0; row < shape.rows; row++) {
      const k = readCell(data[posOf(keyIdx)], row);
      const cid = readCell(data[posOf(clusterIdIdx)], row);
      if (k == null || cid == null) continue;
      out[String(k)] = {
        clusterId: String(cid),
        isCentroid:
          isCentroidIdx === -1 ? false : readNumber(data[posOf(isCentroidIdx)], row) === 1,
        tmDistanceToCentroid:
          tmDistIdx === -1 ? null : readNullableNumber(data[posOf(tmDistIdx)], row),
        tmScoreToCentroid:
          tmScoreIdx === -1 ? null : readNullableNumber(data[posOf(tmScoreIdx)], row),
      };
    }
    clusterMap.value = out;
  });

  const selectedClusterAssignment = computed<ClusterAssignment | undefined>(() =>
    selectedClonotypeKey.value ? clusterMap.value[selectedClonotypeKey.value] : undefined,
  );

  return { selectedClusterAssignment };
}
