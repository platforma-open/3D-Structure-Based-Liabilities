<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const graphState = ref<GraphMakerState>({
  template: "bins",
  title: histogramConfigs.developability.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: histogramConfigs.developability.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="histogramConfigs.developability"
    v-model:graph-state="graphState"
    :p-frame="app.model.outputs.devScorePf"
    :value-spec="app.model.outputs.devScoreSpec"
  />
</template>
