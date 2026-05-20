<script setup lang="ts">
import { getRawPlatformaInstance } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed, ref, watchEffect } from "vue";
import MetricHistogram from "./MetricHistogram.vue";
import StripPlot from "./StripPlot.vue";

// PTable-shaped block-output value. `fullTableHandle` is the `PTableHandle`
// the pFrame driver's `getShape` / `getSpec` / `getData` methods consume.
// We accept `unknown` and narrow at the watchEffect site — the driver
// signatures use a richer handle wrapper we don't import directly.
type PTableOutput = { ok?: boolean; value?: { fullTableHandle?: unknown } } | unknown;

/**
 * Spec R54 distribution view. Below ~20 clonotypes we render a strip plot
 * (each clonotype is its own labeled dot); at or above 20 we render a
 * binned histogram. Both are pure SVG so the column's
 * `pl7.app/graph/thresholds` annotation lands as dashed amber/red
 * vertical lines — graph-maker's histogram template doesn't honour that
 * annotation, which is why the spec R54 threshold-line requirement
 * lives here.
 */
const props = defineProps<{
  /** The scoresTable PTable output. All distribution pages share this
   * single PTable and filter by `columnName` — the driver's getShape /
   * getSpec / getData take a PTableHandle, not a PFrameHandle, so passing
   * per-metric PFrames here wouldn't actually return data. Upstream
   * clonotype labels (`pl7.app/label`) are joined into this table at the
   * model layer, so the strip plot resolves labels from the same fetch. */
  tableOutput: PTableOutput | undefined;
  /** Metric column name to plot, e.g. `pl7.app/liabilities/psh`. Threshold
   * annotations are read from this column's spec. */
  columnName: string;
  /** Section heading. e.g. "PSH — Patches of Surface Hydrophobicity". */
  title: string;
  /** One-paragraph plain-English explanation of what the metric measures
   * and which direction is bad (Raybould-2019-style risk semantics). */
  description: string;
  /** Raybould 2019 / Gordon 2025 amber/red threshold text. Backed by the
   * dashed lines on the chart; left in prose for readers reviewing the
   * page without looking at the plot. */
  thresholds?: string;
  notReadyTitle?: string;
}>();

// Crossover point where histogram becomes more informative than the strip
// plot. Below this the strip plot wins (each candidate visible); above it
// the histogram's distribution-shape signal dominates.
const STRIP_PLOT_THRESHOLD = 20;

type ThresholdEntry = { value: number; color?: string };
type Point = { key: string; value: number };

const points = ref<Point[] | null>(null);
const rowCount = ref<number | null>(null);
const labelMap = ref<Record<string, string>>({});

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

const thresholdEntries = ref<ThresholdEntry[] | undefined>(undefined);

function parseThresholds(annotationRaw: string | undefined): ThresholdEntry[] | undefined {
  if (!annotationRaw) return undefined;
  try {
    const parsed = JSON.parse(annotationRaw) as Array<{ value: number }>;
    if (!Array.isArray(parsed)) return undefined;
    const values = parsed.map((e) => e.value).filter((v) => typeof v === "number");
    if (values.length === 0) return undefined;
    return colorize(values);
  } catch {
    return undefined;
  }
}

// Read per-clonotype values from the scoresTable PTable. The pFrame
// driver's getShape / getSpec / getData take a PTableHandle, not a
// PFrameHandle — that's why earlier per-metric PFrame outputs returned no
// data. Threshold annotations come from the target column's spec inside
// the PTable, so this single fetch covers data + threshold lines.
watchEffect(async () => {
  const tbl = props.tableOutput as
    | { ok?: boolean; value?: { fullTableHandle?: unknown } }
    | undefined;
  if (!tbl?.ok || !tbl.value?.fullTableHandle) {
    points.value = null;
    rowCount.value = null;
    thresholdEntries.value = undefined;
    return;
  }
  const handle = tbl.value.fullTableHandle;
  const driver = getRawPlatformaInstance().pFrameDriver;

  const shape = await driver.getShape(handle as never);
  rowCount.value = shape.rows;
  if (shape.rows === 0) {
    points.value = null;
    thresholdEntries.value = undefined;
    return;
  }

  const spec = await driver.getSpec(handle as never);
  let valueIdx = -1;
  let keyAxisIdx = -1;
  let labelIdx = -1;
  let colAnnotations: Record<string, string> | undefined;
  for (let i = 0; i < spec.length; i++) {
    const entry = spec[i];
    if (entry?.type === "axis" && entry.spec?.name === "pl7.app/vdj/scClonotypeKey") {
      keyAxisIdx = i;
    } else if (entry?.type === "column" && entry.spec?.name === props.columnName) {
      valueIdx = i;
      colAnnotations = entry.spec.annotations;
    } else if (entry?.type === "column" && entry.spec?.name === "pl7.app/label") {
      labelIdx = i;
    }
  }
  thresholdEntries.value = parseThresholds(colAnnotations?.["pl7.app/graph/thresholds"]);
  if (valueIdx === -1) {
    points.value = null;
    return;
  }

  const indices: number[] = [];
  if (keyAxisIdx !== -1) indices.push(keyAxisIdx);
  indices.push(valueIdx);
  if (labelIdx !== -1) indices.push(labelIdx);
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

  const keyColData = keyAxisIdx === -1 ? undefined : data[0];
  const valueColData = data[keyAxisIdx === -1 ? 0 : 1];
  const labelColData = labelIdx === -1 ? undefined : data[indices.length - 1];

  const out: Point[] = [];
  const map: Record<string, string> = {};
  for (let row = 0; row < shape.rows; row++) {
    const v = readCell(valueColData, row);
    if (v === null || Number.isNaN(Number(v))) continue;
    const key = keyColData ? String(readCell(keyColData, row) ?? row) : String(row + 1);
    out.push({ key, value: Number(v) });
    const lab = labelColData ? readCell(labelColData, row) : null;
    if (key && lab !== null && lab !== undefined) map[key] = String(lab);
  }
  points.value = out;
  labelMap.value = map;
});

// Apply the label map on top of the raw points so the strip plot shows
// clone names; falls through to the axis key when the label is missing.
const pointsWithLabels = computed<Point[] | null>(() => {
  if (!points.value) return null;
  return points.value.map((p) => ({
    key: labelMap.value[p.key] ?? p.key,
    value: p.value,
  }));
});

const useStripPlot = computed(
  () =>
    points.value !== null && points.value.length > 0 && points.value.length < STRIP_PLOT_THRESHOLD,
);

const useHistogram = computed(
  () => points.value !== null && points.value.length >= STRIP_PLOT_THRESHOLD,
);

const histogramValues = computed<number[]>(() => points.value?.map((p) => p.value) ?? []);

const stripPlotAxisLabel = computed(() => {
  const n = points.value?.length ?? 0;
  return `${n} clonotype${n === 1 ? "" : "s"} (each dot = one clonotype; dashed lines = Raybould / Gordon thresholds)`;
});

const histogramAxisLabel = computed(() => {
  const n = points.value?.length ?? 0;
  return `${n} clonotypes (dashed lines = Raybould / Gordon thresholds)`;
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
      v-if="useStripPlot && pointsWithLabels"
      :points="pointsWithLabels"
      :thresholds="thresholdEntries"
      :axis-label="stripPlotAxisLabel"
    />

    <MetricHistogram
      v-else-if="useHistogram"
      :values="histogramValues"
      :thresholds="thresholdEntries"
      :axis-label="histogramAxisLabel"
    />

    <p v-else :style="{ fontSize: '14px', color: '#6b7280', marginTop: '12px' }">
      {{
        notReadyTitle ??
        "Run the workflow on a predicted-structures dataset to see the distribution"
      }}
    </p>
  </PlBlockPage>
</template>
