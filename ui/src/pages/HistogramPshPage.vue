<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="PSH — Patches of Surface Hydrophobicity"
    description="Surface-area-weighted hydrophobicity in the CDR vicinity (Raybould 2019, spec R25). Computed as Σ H(R₁)·H(R₂) / r₁₂² over all surface-exposed residue pairs within 7.5 Å heavy-atom distance, using Kyte-Doolittle hydrophobicity normalized to [1.0, 2.0]. High = sticky surfaces → aggregation, viscosity at high concentration, non-specific binding. Very low = suspiciously hydrophilic (also flagged). Bidirectional risk."
    thresholds="Green ~100–156. Amber 84–100 or 156–174. Red < 84 or > 174."
    :pframe="app.model.outputs.pshPf"
    :spec="app.model.outputs.pshSpec"
    :state="app.model.data.graphStatePshV2"
    @update:state="(v) => (app.model.data.graphStatePshV2 = v)"
  />
</template>
