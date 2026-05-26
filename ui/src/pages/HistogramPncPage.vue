<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
const graphState = ref<GraphMakerState>({
  template: "bins",
  title: histogramConfigs.pnc.title,
  currentTab: null,
  layersSettings: { bins: { fillColor: histogramConfigs.pnc.fillColor } },
});
</script>

<template>
  <HistogramPage
    v-bind="histogramConfigs.pnc"
    v-model:graph-state="graphState"
    :p-frame="app.model.outputs.pncPf"
    :value-spec="app.model.outputs.pncSpec"
  />
</template>
