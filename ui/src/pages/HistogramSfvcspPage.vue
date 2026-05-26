<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const graphState = ref<GraphMakerState>({
  template: "bins",
  title: histogramConfigs.sfvcsp.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: histogramConfigs.sfvcsp.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="histogramConfigs.sfvcsp"
    v-model:graph-state="graphState"
    :p-frame="app.model.outputs.sfvcspPf"
    :value-spec="app.model.outputs.sfvcspSpec"
  />
</template>
