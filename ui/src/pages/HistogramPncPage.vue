<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";
import { histogramConfigs } from "./histogramConfigs";

const app = useApp();
</script>

<template>
  <HistogramPage v-bind="histogramConfigs.pnc" :table-output="app.model.outputs.scoresTable" />
</template>
