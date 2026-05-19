<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { PColumnIdAndSpec } from "@platforma-sdk/model";
import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed, ref, watchEffect } from "vue";
import StripPlot from "./StripPlot.vue";

// GraphMaker's `pFrame` prop expects `OutputWithStatus<PFrameHandle>` from
// pl-model-common. BlockOutputs adds an `__unwrap: false` marker that's
// incompatible with that prop shape; accept `unknown` and cast at the call
// site. Runtime contract is duck-typed (GraphMaker reads `.ok` / `.value`).
type PFrameOutput = { ok?: boolean; value?: { fullTableHandle?: unknown } } | unknown;

/**
 * Spec R54 distribution view. Below ~20 clonotypes we render an SVG strip
 * plot (each clonotype is its own labeled dot, plus dashed Raybould 2019 /
 * Gordon 2025 threshold lines). At ≥20 clonotypes we fall back to
 * graph-maker's histogram template — distribution shape becomes meaningful.
 *
 * The histogram path doesn't honour `pl7.app/graph/thresholds` annotations
 * yet (only scatter does), so the strip-plot path is also where R54
 * threshold lines actually render today.
 */
const props = defineProps<{
  pframe: PFrameOutput | undefined;
  spec: PColumnIdAndSpec | undefined;
  state: GraphMakerState;
  /** Section heading. e.g. "PSH — Patches of Surface Hydrophobicity". */
  title: string;
  /** One-paragraph plain-English explanation of what the metric measures
   * and which direction is bad (Raybould-2019-style risk semantics). */
  description: string;
  /** Raybould 2019 / Gordon 2025 amber/red threshold text. Visible as
   * dashed lines in the strip plot; histogram falls back to this prose. */
  thresholds?: string;
  notReadyTitle?: string;
}>();
const emit = defineEmits<{
  "update:state": [GraphMakerState];
}>();

const stateModel = computed({
  get: () => props.state,
  set: (v: GraphMakerState) => emit("update:state", v),
});

const defaults = computed((): PredefinedGraphOption<"histogram">[] | undefined => {
  if (!props.spec?.spec) return undefined;
  return [{ inputName: "value", selectedSource: props.spec.spec }];
});

// Crossover point where histogram becomes more informative than the strip
// plot. Below this the strip plot wins (each candidate visible); above it
// the histogram's distribution-shape signal dominates.
const STRIP_PLOT_THRESHOLD = 20;

type ThresholdEntry = { value: number; color?: string };
type Point = { key: string; value: number };

const points = ref<Point[] | null>(null);
const rowCount = ref<number | null>(null);

// Raybould 2019 threshold sets are amber/red bands on either side of the
// optimum (one-sided metrics like PSH/PPC/PNC just have an amber + red
// upper cut). Color by position in the list: 4 entries → bidirectional
// (red-low, amber-low, amber-high, red-high); 2 entries → one-sided
// (amber, red).
const RED = "#dc2626";
const AMBER = "#d97706";
function colorize(values: number[]): ThresholdEntry[] {
  if (values.length === 4) {
    return [
      { value: values[0], color: RED },
      { value: values[1], color: AMBER },
      { value: values[2], color: AMBER },
      { value: values[3], color: RED },
    ];
  }
  if (values.length === 2) {
    return [
      { value: values[0], color: AMBER },
      { value: values[1], color: RED },
    ];
  }
  return values.map((v) => ({ value: v }));
}

const thresholdEntries = computed<ThresholdEntry[] | undefined>(() => {
  const raw = props.spec?.spec?.annotations?.["pl7.app/graph/thresholds"];
  if (!raw) return undefined;
  try {
    const parsed = JSON.parse(raw) as Array<{ value: number }>;
    if (!Array.isArray(parsed)) return undefined;
    const values = parsed.map((e) => e.value).filter((v) => typeof v === "number");
    if (values.length === 0) return undefined;
    return colorize(values);
  } catch {
    return undefined;
  }
});

// Pull per-clonotype values for the strip plot. Reuses the pframe driver in
// the same shape as MainPage's R44/R45 alerts: watchEffect tracks the
// reactive deps before the first await, anything after is fire-and-forget.
watchEffect(async () => {
  const pf = props.pframe as { ok?: boolean; value?: { fullTableHandle?: unknown } } | undefined;
  if (!pf?.ok || !pf.value?.fullTableHandle) {
    points.value = null;
    rowCount.value = null;
    return;
  }
  const handle = pf.value.fullTableHandle;
  const driver = getRawPlatformaInstance().pFrameDriver;

  // Type assertions are pragmatic here — driver signatures from
  // pl-pframe-driver use a richer PTableHandle wrapper. The runtime
  // contract reads / passes the same opaque value.
  const shape = await driver.getShape(handle as never);
  rowCount.value = shape.rows;
  if (shape.rows === 0 || shape.rows > STRIP_PLOT_THRESHOLD) {
    points.value = null;
    return;
  }

  const spec = await driver.getSpec(handle as never);
  const targetColName = props.spec?.spec?.name;
  let valueIdx = -1;
  let keyAxisIdx = -1;
  for (let i = 0; i < spec.length; i++) {
    const entry = spec[i];
    if (entry?.type === "axis" && entry.spec?.name === "pl7.app/vdj/scClonotypeKey") {
      keyAxisIdx = i;
    } else if (entry?.type === "column" && entry.spec?.name === targetColName) {
      valueIdx = i;
    }
  }
  if (valueIdx === -1) {
    points.value = null;
    return;
  }

  const indices = keyAxisIdx === -1 ? [valueIdx] : [keyAxisIdx, valueIdx];
  const data = await driver.getData(handle as never, indices, { offset: 0, length: shape.rows });
  // pFrame driver returns column-major data. Long/String columns come back
  // as either a TypedArray, plain array, or a numeric-indexed wrapper object.
  function readCell(col: { data?: unknown } | undefined, i: number): string | number | null {
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

  const valueCol = keyAxisIdx === -1 ? data[0] : data[1];
  const keyCol = keyAxisIdx === -1 ? undefined : data[0];
  const out: Point[] = [];
  for (let row = 0; row < shape.rows; row++) {
    const v = readCell(valueCol, row);
    if (v === null || Number.isNaN(Number(v))) continue;
    const key = keyCol ? String(readCell(keyCol, row) ?? row) : String(row + 1);
    out.push({ key, value: Number(v) });
  }
  points.value = out;
});

const useStripPlot = computed(
  () =>
    points.value !== null && points.value.length > 0 && points.value.length < STRIP_PLOT_THRESHOLD,
);

const stripPlotAxisLabel = computed(() => {
  const n = points.value?.length ?? 0;
  return `${n} clonotype${n === 1 ? "" : "s"} (each dot = one clonotype; dashed lines = Raybould / Gordon thresholds)`;
});
</script>

<template>
  <PlBlockPage :title="title">
    <p :style="{ fontSize: '13px', color: '#374151', marginTop: '8px', lineHeight: '1.5' }">
      {{ description }}
    </p>
    <p
      v-if="thresholds"
      :style="{
        fontSize: '12px',
        color: '#6b7280',
        marginTop: '4px',
        fontStyle: 'italic',
        lineHeight: '1.5',
      }"
    >
      <strong>Thresholds:</strong> {{ thresholds }}
    </p>

    <StripPlot
      v-if="useStripPlot && points"
      :points="points"
      :thresholds="thresholdEntries"
      :axis-label="stripPlotAxisLabel"
    />

    <template v-else>
      <p
        v-if="rowCount !== null && rowCount > 0 && rowCount < STRIP_PLOT_THRESHOLD"
        :style="{
          fontSize: '11px',
          color: '#a16207',
          background: 'rgba(252, 211, 77, 0.15)',
          border: '1px solid rgba(252, 211, 77, 0.4)',
          borderRadius: '4px',
          padding: '6px 10px',
          marginTop: '8px',
          marginBottom: '12px',
          lineHeight: '1.5',
        }"
      >
        <strong>Note on histogram interpretation at small N:</strong> below ~20 clonotypes each bar
        represents one (or a few) clonotypes, not a distribution shape. Read individual values from
        the Main table instead. Histograms are calibrated against the Raybould 2019 cohort of 242
        antibodies — they become informative once your dataset reaches that scale.
      </p>
      <!-- GraphMaker's pFrame prop is required (typed OutputWithStatus<PFrameHandle>,
           non-nullable). Hide the component entirely while the upstream is
           pending — gives the user a quiet page instead of a typed crash. -->
      <GraphMaker
        v-if="pframe"
        v-model="stateModel"
        chart-type="histogram"
        :data-state-key="pframe as never"
        :p-frame="pframe as never"
        :default-options="defaults"
        :status-text="{
          noPframe: {
            title:
              notReadyTitle ??
              'Run the workflow on a predicted-structures dataset to see the distribution',
          },
        }"
      />
      <p v-else :style="{ fontSize: '14px', color: '#6b7280', marginTop: '12px' }">
        {{
          notReadyTitle ??
          "Run the workflow on a predicted-structures dataset to see the distribution"
        }}
      </p>
    </template>
  </PlBlockPage>
</template>
