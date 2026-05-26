<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const graphState = ref<GraphMakerState>({
  template: "bins",
  title: histogramConfigs.cdrh3Compactness.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: histogramConfigs.cdrh3Compactness.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="histogramConfigs.cdrh3Compactness"
    v-model:graph-state="graphState"
    :p-frame="app.model.outputs.cdrh3CompactnessPf"
    :value-spec="app.model.outputs.cdrh3CompactnessSpec"
  />
</template>
