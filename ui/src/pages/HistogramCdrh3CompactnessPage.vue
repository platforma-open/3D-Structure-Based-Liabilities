<script setup lang="ts">
import { useApp } from "../app";
import HistogramPage from "../components/HistogramPage.vue";

const app = useApp();
</script>

<template>
  <HistogramPage
    title="CDRH3 compactness (VHH only)"
    description="CDR3 length divided by its radius (spec R30, VHH/TNP mode only). Radius ρ is the distance between centroids of CDR3 Cα atoms (IMGT 105–117) and IMGT anchor Cα atoms (102, 103, 118, 119). Bidirectional: too compact suggests an unfolded or aberrant CDR3, too elongated suggests aggregation-prone loops. IMGT numbering required — falls back to the scheme-aware ranges in other schemes."
    thresholds="Green 0.82–1.57. Amber 0.56–0.82 or 1.57–1.61. Red < 0.56 or > 1.61."
    not-ready-title="CDRH3 compactness is only computed in VHH (TNP) mode. Run the block on a VHH dataset to populate this distribution."
    :labels-pf="app.model.outputs.clonotypeLabelsPf"
    :pframe="app.model.outputs.cdrh3CompactnessPf"
    :spec="app.model.outputs.cdrh3CompactnessSpec"
    :state="app.model.data.graphStateCdrh3CompactnessV2"
    @update:state="(v) => (app.model.data.graphStateCdrh3CompactnessV2 = v)"
  />
</template>
