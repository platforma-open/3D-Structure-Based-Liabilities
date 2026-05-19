<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="Developability score — composite engineering burden"
    description="R41 composite. Sum of three contributions: (1) motif structural risk score — Σ over surfaced motifs of fixability × region × exposure (R20); (2) per-metric flag bumps — red = 8, amber = 3, green = 0 across PSH/PPC/PNC/SFvCSP/CDRH3 compactness/totalCdrLength; (3) cysteine penalties — exposedExtraCysCount × 8 + brokenCanonicalDisulfideCount × 20 + missingCanonicalCysCount × 20. Higher = more engineering work to bring the candidate to clinic. There is no pass/fail cut — use this for ranking candidates against each other; the categorical Developability risk and Integrity risk columns on the Main table apply the spec R41a rules and are easier to read at a glance."
    :labels-pf="app.model.outputs.clonotypeLabelsPf"
    :pframe="app.model.outputs.devScorePf"
    :spec="app.model.outputs.devScoreSpec"
    :state="app.model.data.graphStateDevScoreV2"
    @update:state="(v) => (app.model.data.graphStateDevScoreV2 = v)"
  />
</template>
