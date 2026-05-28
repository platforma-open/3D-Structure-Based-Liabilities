<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";

// Spec R54 distribution view. Renders one per-metric histogram via
// graph-maker. Amber/red threshold lines come from the metric column's
// `pl7.app/graph/thresholds` annotation, honored by the histogram
// template (graph-maker 1.4.3+, miplots4 transitively).
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
    <div :style="{ height: '500px', marginTop: '12px' }">
      <GraphMaker
        v-model="graphStateModel"
        chartType="histogram"
        :p-frame="pFrame"
        :default-options="defaultOptions"
        :status-text="{
          noPframe: {
            title: notReadyTitle ?? 'Run on a predicted-structures dataset to see the distribution',
          },
        }"
      />
    </div>
  </PlBlockPage>
</template>
