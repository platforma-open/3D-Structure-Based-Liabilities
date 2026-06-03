<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import type { ThresholdBands } from "../pages/histogramConfigs";

const props = defineProps<{
  // `title` is shown by PlBlockPage as the page heading. Each per-metric page
  // sets the chart's own title to "" via makeGraphState so it doesn't show
  // twice.
  title: string;
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
  return !!(t && (t.green || t.amber || t.red));
});
</script>

<template>
  <PlBlockPage :title="title">
    <div v-if="hasLegend && thresholds" class="threshold-legend" aria-label="Threshold bands">
      <span v-if="thresholds.green" class="threshold-pill threshold-pill--green">
        Pass: {{ thresholds.green }}
      </span>
      <span v-if="thresholds.amber" class="threshold-pill threshold-pill--amber">
        Borderline: {{ thresholds.amber }}
      </span>
      <span v-if="thresholds.red" class="threshold-pill threshold-pill--red">
        Fail: {{ thresholds.red }}
      </span>
    </div>

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
    />
  </PlBlockPage>
</template>

<style scoped>
.threshold-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 12px;
}

.threshold-pill {
  padding: 2px 10px;
  border-radius: 12px;
  font-weight: 500;
  border: 1px solid transparent;
}

.threshold-pill--green {
  background: #ecfdf5;
  border-color: #a7f3d0;
  color: #065f46;
}

.threshold-pill--amber {
  background: #fffbeb;
  border-color: #fcd34d;
  color: #92400e;
}

.threshold-pill--red {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #991b1b;
}
</style>
