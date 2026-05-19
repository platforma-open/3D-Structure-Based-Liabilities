<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="PNC — Patches of Negative Charge"
    description="Surface-area-weighted negative-charge density in the CDR vicinity (Raybould 2019, spec R26). Pair formula sums over D/E pairs within 7.5 Å heavy-atom distance. Salt-bridge residues zeroed. High = expression heterogeneity, charge variants under cation-exchange or imaging cIEF analytics, and similar PK concerns as PPC at high values."
    thresholds="Green ≤ 1.84. Amber 1.84–3.50. Red > 3.50."
    :pframe="app.model.outputs.pncPf"
    :spec="app.model.outputs.pncSpec"
    :state="app.model.data.graphStatePncV2"
    @update:state="(v) => (app.model.data.graphStatePncV2 = v)"
  />
</template>
