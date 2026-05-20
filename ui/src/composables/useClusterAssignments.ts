import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { computed, ref, watchEffect, type ComputedRef, type Ref } from "vue";
import { readCell, readNumber, readString } from "./ptableCell";

/**
 * Spec R42 — per-clonotype cluster assignment row, lifted out of the
 * scoresTable PTable. Populated only when the 3D Structure Clustering
 * block is upstream (it auto-joins these columns on the scClonotypeKey
 * axis); otherwise the map stays empty and the UI hides cluster bits.
 */
export type ClusterAssignment = {
  clusterId: string;
  isCentroid: boolean;
  tmDistanceToCentroid: number | null;
  tmScoreToCentroid: number | null;
};

/** Output value shape of `outputs.scoresTable` — `OutputWithStatus<PlDataTableV2>`. */
type ScoresTableOutput = { ok?: boolean; value?: { fullTableHandle?: unknown } } | undefined;

/**
 * Subscribe to the scoresTable PTable and rebuild a per-clonotype cluster
 * assignment map whenever it changes. Returns the live map plus a couple
 * of derived computeds the UI uses.
 *
 * `selectedClonotypeKey` and `centroidsOnly` are passed in (rather than
 * created inside) because they're owned by MainPage's selection state —
 * we want the same refs the dropdown writes to.
 */
export function useClusterAssignments(
  scoresTable: ComputedRef<ScoresTableOutput>,
  selectedClonotypeKey: Ref<string | null>,
  centroidsOnly: Ref<boolean>,
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
          tmDistIdx === -1
            ? null
            : readString(data[posOf(tmDistIdx)], row) === null
              ? null
              : readNumber(data[posOf(tmDistIdx)], row),
        tmScoreToCentroid:
          tmScoreIdx === -1
            ? null
            : readString(data[posOf(tmScoreIdx)], row) === null
              ? null
              : readNumber(data[posOf(tmScoreIdx)], row),
      };
    }
    clusterMap.value = out;
  });

  // When "Centroids only" is toggled on and the current selection isn't a
  // centroid, jump to the centroid of the same cluster so the viewer
  // doesn't show a hidden row.
  watchEffect(() => {
    if (!centroidsOnly.value) return;
    const key = selectedClonotypeKey.value;
    if (!key) return;
    const cmap = clusterMap.value;
    const current = cmap[key];
    if (current?.isCentroid) return;
    const sameClusterCentroid = Object.entries(cmap).find(
      ([, a]) => a.clusterId === current?.clusterId && a.isCentroid,
    );
    if (sameClusterCentroid) selectedClonotypeKey.value = sameClusterCentroid[0];
  });

  const hasClusterData = computed(() => Object.keys(clusterMap.value).length > 0);
  const selectedClusterAssignment = computed<ClusterAssignment | undefined>(() =>
    selectedClonotypeKey.value ? clusterMap.value[selectedClonotypeKey.value] : undefined,
  );

  return { clusterMap, hasClusterData, selectedClusterAssignment };
}
