<script setup lang="ts">
import type { GraphMakerState, PredefinedGraphOption } from "@milaboratories/graph-maker";
import { GraphMaker } from "@milaboratories/graph-maker";
import type { OutputWithStatus, PColumnIdAndSpec, PFrameHandle } from "@platforma-sdk/model";
import { PlBlockPage } from "@platforma-sdk/ui-vue";
import { computed } from "vue";

const props = defineProps<{
  // `title` is declared so it is consumed from the spread config rather than
  // falling through onto PlBlockPage; the title shows on the chart itself
  // (via the graph state), not as a page header.
  title: string;
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
    />
  </PlBlockPage>
</template>
