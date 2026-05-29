<script setup lang="ts">
import type { GraphMakerState } from "@milaboratories/graph-maker";
import { computed, ref } from "vue";
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs, makeGraphState } from "./histogramConfigs";

const app = useApp();
const mode = computed(() => app.model.outputs.detectedMode);

const config = computed(() =>
  mode.value === "TNP" ? histogramConfigs.cdrh3Compactness : histogramConfigs.sfvcsp,
);
const pFrame = computed(() =>
  mode.value === "TNP" ? app.model.outputs.cdrh3CompactnessPf : app.model.outputs.sfvcspPf,
);
const valueSpec = computed(() =>
  mode.value === "TNP" ? app.model.outputs.cdrh3CompactnessSpec : app.model.outputs.sfvcspSpec,
);

const graphState = ref<GraphMakerState>(makeGraphState(config.value));
</script>

<template>
  <HistogramPage
    v-bind="config"
    v-model:graph-state="graphState"
    :p-frame="pFrame"
    :value-spec="valueSpec"
  />
</template>
