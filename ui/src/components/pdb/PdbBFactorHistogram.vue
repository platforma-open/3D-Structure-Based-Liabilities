<script setup lang="ts">
/**
 * PdbBFactorHistogram
 * -------------------
 * Distribution of every atom's B-factor across the whole structure, drawn
 * by the SDK's `PlChartHistogram` (d3 under the hood). 40 bins by default,
 * which gives enough resolution to see the typical bimodal pattern (rigid
 * core vs. flexible loops) without becoming spiky.
 */
import { PlChartHistogram } from "@platforma-sdk/ui-vue";

defineProps<{ values: number[] }>();
</script>

<template>
  <h3>B-factor distribution</h3>
  <PlChartHistogram
    v-if="values.length"
    :settings="{
      type: 'basic',
      numbers: values,
      nBins: 40,
      xAxisLabel: 'B-factor',
      yAxisLabel: 'Atoms',
    }"
  />
</template>
