<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="SFvCSP — Symmetry of Fv Charges Product"
    description="Inter-chain charge symmetry (Raybould 2019, spec R28; paired-Fv mode only). Computed as (Σ Q on surface-exposed VH residues) × (Σ Q on surface-exposed VL residues) over the whole V-domain, not CDR-restricted. Salt-bridge residues zeroed. Very negative = strongly asymmetric charges between heavy and light chains → viscosity at high concentration (typical at ≥ 100 mg/mL formulations)."
    thresholds="Green ≥ −6.3. Amber −20.4 to −6.3. Red < −20.4."
    not-ready-title="SFvCSP is only computed in paired-Fv (TAP) mode. Run the block on a paired-Fv dataset to populate this distribution."
    :table-output="app.model.outputs.scoresTable"
    column-name="pl7.app/liabilities/sfvcsp"
  />
</template>
