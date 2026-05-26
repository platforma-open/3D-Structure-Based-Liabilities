<script setup lang="ts">
import { createPlDataTableStateV2 } from "@platforma-sdk/model";
import { PlAgDataTableV2, PlBlockPage, usePlDataTableSettingsV2 } from "@platforma-sdk/ui-vue";
import { ref } from "vue";
import { useApp } from "../app";

const app = useApp();

// Spec R21-R23 cysteine drill-down. Own page (same reason as Motifs).
const cysTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.cysTable,
  sourceId: () => "cysteines-v4",
});
const cysLocalState = ref(createPlDataTableStateV2());
</script>

<template>
  <PlBlockPage title="3D Structure-Based Liabilities · Cysteines">
    <h3 :style="{ margin: '12px 0 6px' }">Cysteine state</h3>
    <p :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }">
      Every Cys residue with its disulfide-bond partner (SG-SG ≤ 3.0 Å and Cα-Cα ≤ 7.0 Å). When a
      numbering scheme + chain role are set, each Cys is classified per spec R21-R23:
      <code>disulfide</code>, <code>disulfide_broken</code>, <code>disulfide_missing</code> (phantom
      row at the expected position), or <code>cys_extra</code>.
    </p>
    <div :style="{ height: 'calc(100vh - 220px)', flexShrink: 0 }">
      <PlAgDataTableV2
        v-model="cysLocalState"
        :settings="cysTableSettings"
        not-ready-text="Run on a PDB / dataset to see cysteine state"
        no-rows-text="No cysteines found"
      />
    </div>
  </PlBlockPage>
</template>
