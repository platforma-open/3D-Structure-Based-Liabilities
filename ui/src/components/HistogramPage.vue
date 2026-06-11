<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import type { ThresholdBands } from "../pages/histogramConfigs";

// The page wrappers spread the whole config; keys that aren't declared props
// (title / columnName / fillColor) feed makeGraphState, not this component.
// Drop them rather than let `title` fall through to PlBlockPage as a second
// page heading: graph-maker's own title (from its v-model state) is the only
// title we want.
defineOptions({ inheritAttrs: false });

const props = defineProps<{
  // No PlBlockPage title: the chart's own title (graph-maker v-model state)
  // carries the page label. Threshold lines are drawn by graph-maker from the
  // value column's `pl7.app/graph/thresholds` annotation; the legend below
  // maps the bands those lines delimit.
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
  <PlBlockPage no-body-gutters>
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
