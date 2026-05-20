<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="PPC — Patches of Positive Charge"
    description="Surface-area-weighted positive-charge density in the CDR vicinity (Raybould 2019, spec R26). Same pair formula as PSH but with charge magnitudes — sums over K/R/H pairs within 7.5 Å heavy-atom distance, using D/E=−1, K/R=+1, H=+0.1. Salt-bridge residues (R15a) zeroed. High = faster clearance (PK risk), non-specific receptor binding (FcRn, polyspecificity panels)."
    thresholds="Green ≤ 1.25. Amber 1.25–3.16. Red > 3.16."
    :table-output="app.model.outputs.scoresTable"
    column-name="pl7.app/liabilities/ppc"
  />
</template>
