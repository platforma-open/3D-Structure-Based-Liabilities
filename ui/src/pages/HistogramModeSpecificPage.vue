<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { computed, ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { useDetectedMode } from "../composables/useDetectedMode";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const scoresPf = computed(() => {
  const t = app.model.outputs.scoresTable;
  return t?.ok && t.value ? t.value.fullPframeHandle : undefined;
});
const { mode } = useDetectedMode(scoresPf);

const config = computed(() =>
  mode.value === "TNP" ? histogramConfigs.cdrh3Compactness : histogramConfigs.sfvcsp,
);
const pFrame = computed(() =>
  mode.value === "TNP" ? app.model.outputs.cdrh3CompactnessPf : app.model.outputs.sfvcspPf,
);
const valueSpec = computed(() =>
  mode.value === "TNP" ? app.model.outputs.cdrh3CompactnessSpec : app.model.outputs.sfvcspSpec,
);

const graphState = ref<GraphMakerState>({
  template: "bins",
  title: config.value.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: config.value.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="config"
    v-model:graph-state="graphState"
    :p-frame="pFrame"
    :value-spec="valueSpec"
  />
</template>
