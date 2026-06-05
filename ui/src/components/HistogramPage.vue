<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import type { ThresholdBands } from "../pages/histogramConfigs";

const props = defineProps<{
  // No page heading rendered. The section nav already labels the page;
  // the threshold legend lives inside graph-maker's titleLineSlot so it
  // sits next to the chart title bar instead of pushing the chart down.
  notReadyTitle?: string;
  thresholds?: ThresholdBands;
  pFrame: OutputWithStatus<PFrameHandle>;
  valueSpec: PColumnIdAndSpec | undefined;
  graphState: GraphMakerState;
}>();

const emit = defineEmits<(e: "update:graphState", value: GraphMakerState) => void>();

const graphStateModel = computed<GraphMakerState>({
  get: () => props.graphState,
  set: (v) => emit("update:graphState", v),
});

const defaultOptions = computed<PredefinedGraphOption<"histogram">[] | undefined>(() => {
  if (!props.valueSpec) return undefined;
  return [{ inputName: "value", selectedSource: props.valueSpec.spec }];
});

const hasLegend = computed(() => {
  const t = props.thresholds;
  return !!(t && (t.none || t.medium || t.high));
});
</script>

<template>
  <PlBlockPage>
    <GraphMaker
      v-model="graphStateModel"
      chart-type="histogram"
      :data-state-key="pFrame"
      :p-frame="pFrame"
      :default-options="defaultOptions"
      :status-text="{
        noPframe: {
          title: notReadyTitle ?? 'Run on a 3D structures dataset to see the distribution',
        },
      }"
    >
      <template #titleLineSlot>
        <div v-if="hasLegend && thresholds" class="threshold-legend" aria-label="Threshold bands">
          <span v-if="thresholds.none" class="threshold-item">
            <span class="threshold-dot threshold-dot--none" />
            <span class="threshold-label">None</span>
            <span class="threshold-range">{{ thresholds.none }}</span>
          </span>
          <span v-if="thresholds.medium" class="threshold-item">
            <span class="threshold-dot threshold-dot--medium" />
            <span class="threshold-label">Medium</span>
            <span class="threshold-range">{{ thresholds.medium }}</span>
          </span>
          <span v-if="thresholds.high" class="threshold-item">
            <span class="threshold-dot threshold-dot--high" />
            <span class="threshold-label">High</span>
            <span class="threshold-range">{{ thresholds.high }}</span>
          </span>
        </div>
      </template>
    </GraphMaker>
  </PlBlockPage>
</template>

<style>
/* Graph-maker's `.chart_titleLineSlot` defaults to `margin-left: auto`,
   which pins the slot to the right edge of `.chart_header`. Flip it so
   our threshold legend sits next to the chart title on the left. Global
   (unscoped) is intentional: the rule has to land on the lib's slot
   wrapper, which scoped styles can't reach from inside the slot. */
.chart_titleLineSlot {
  margin-left: 12px;
  margin-right: auto;
}
</style>

<style scoped>
.threshold-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--txt-02, #4a5560);
}

.threshold-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.threshold-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 8px;
}

.threshold-dot--none {
  background: #16a34a;
}

.threshold-dot--medium {
  background: #d97706;
}

.threshold-dot--high {
  background: #dc2626;
}

.threshold-label {
  font-weight: 500;
  color: var(--txt-01, #0f172a);
}

.threshold-range {
  color: var(--txt-03, #6b7280);
  font-variant-numeric: tabular-nums;
}
</style>
