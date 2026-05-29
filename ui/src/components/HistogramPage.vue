<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";

// Renders one per-metric histogram via graph-maker. Amber/red threshold
// lines come from the metric column's `pl7.app/graph/thresholds` annotation,
// honored by the histogram template.
const props = defineProps<{
  title: string;
  description: string;
  thresholds?: string;
  notReadyTitle?: string;
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
</script>

<template>
  <PlBlockPage :title="title">
    <p class="description">{{ description }}</p>
    <p v-if="thresholds" class="thresholds"><strong>Thresholds:</strong> {{ thresholds }}</p>
    <div class="chart">
      <GraphMaker
        v-model="graphStateModel"
        chartType="histogram"
        :p-frame="pFrame"
        :default-options="defaultOptions"
        :status-text="{
          noPframe: {
            title: notReadyTitle ?? 'Run on a 3D structures dataset to see the distribution',
          },
        }"
      />
    </div>
  </PlBlockPage>
</template>

<style scoped>
.description {
  margin-top: 8px;
  line-height: 1.5;
}
.thresholds {
  margin-top: 4px;
  font-style: italic;
  line-height: 1.5;
  color: var(--txt-mask, #6b7280);
}
.chart {
  height: 500px;
  margin-top: 12px;
}
</style>
