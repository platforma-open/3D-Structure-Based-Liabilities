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
          <span v-if="thresholds.none" class="threshold-pill threshold-pill--none">
            None: {{ thresholds.none }}
          </span>
          <span v-if="thresholds.medium" class="threshold-pill threshold-pill--medium">
            Medium: {{ thresholds.medium }}
          </span>
          <span v-if="thresholds.high" class="threshold-pill threshold-pill--high">
            High: {{ thresholds.high }}
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
  gap: 8px;
  font-size: 12px;
}

.threshold-pill {
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 500;
  border: 1px solid transparent;
}

.threshold-pill--none {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #065f46;
}

.threshold-pill--medium {
  background: #fffbeb;
  border-color: #fcd34d;
  color: #92400e;
}

.threshold-pill--high {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}
</style>
