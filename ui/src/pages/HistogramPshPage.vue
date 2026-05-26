<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const graphState = ref<GraphMakerState>({
  template: "bins",
  title: histogramConfigs.psh.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: histogramConfigs.psh.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="histogramConfigs.psh"
    v-model:graph-state="graphState"
    :p-frame="app.model.outputs.pshPf"
    :value-spec="app.model.outputs.pshSpec"
  />
</template>
