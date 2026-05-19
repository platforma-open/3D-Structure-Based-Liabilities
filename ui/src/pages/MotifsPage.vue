<script setup lang="ts">
import { createPlDataTableStateV2 } from "@platforma-sdk/model";
import { PlAgDataTableV2, PlBlockPage, usePlDataTableSettingsV2 } from "@platforma-sdk/ui-vue";
import { ref } from "vue";
import { useApp } from "../app";

const app = useApp();

// Spec R51 motif drill-down — one row per surfaced motif hit. Lives on
// its own page so a single PlAgDataTableV2 mounts at a time (multi-table
// pages cause a stale-state cascade where AG-Grid sticks in placeholder).
const motifsTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.motifsTable,
  sourceId: () => "motifs-v3",
});
const motifsLocalState = ref(createPlDataTableStateV2());

// Spec R12 — Raybould 2019 canonical cutoff. rSASA below this is "buried".
const BURIED_CUTOFF = 0.075;
</script>

<template>
  <PlBlockPage title="3D Structure-Based Liabilities · Motifs">
    <h3 :style="{ margin: '12px 0 6px' }">Surface-exposed liability motifs</h3>
    <p :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }">
      One row per surfaced motif hit. On the predicted-structures path each clonotype contributes
      its own rows (Clonotype ID is the leading axis). Buried matches (rSASA &lt;
      {{ BURIED_CUTOFF }}) are dropped upstream and never appear here.
    </p>
    <div :style="{ height: 'calc(100vh - 220px)', flexShrink: 0 }">
      <PlAgDataTableV2
        v-model="motifsLocalState"
        :settings="motifsTableSettings"
        not-ready-text="Run on a PDB / dataset to see surfaced motifs"
        no-rows-text="No surface-exposed motifs detected"
      />
    </div>
  </PlBlockPage>
</template>
