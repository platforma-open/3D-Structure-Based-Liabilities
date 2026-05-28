<script setup lang="ts">
import type { PlStructureViewerProps } from "@milaboratories/structure-viewer";
import { PlStructureViewer } from "@milaboratories/structure-viewer";
import type { PFrameHandle, PTableKey } from "@platforma-sdk/model";
import { createPlDataTableStateV2 } from "@platforma-sdk/model";
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDatasetSelector,
  PlDropdown,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  PlTextField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watch } from "vue";
import { useApp } from "../app";

import { useClonotypeLabels } from "../composables/useClonotypeLabels";
import { useDetectedMode } from "../composables/useDetectedMode";
import { useClusterAssignments } from "../composables/useClusterAssignments";
import { useRunSummaryAlerts } from "../composables/useRunSummaryAlerts";
import { pfHandleFrom } from "../composables/ptableCell";

const app = useApp();

// Spec R51 primary view. `sourceId` is versioned so a shape change on
// the underlying PColumn invalidates AG-Grid's column-order cache.
const scoresTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.scoresTable,
  sourceId: () => "scores-v2",
});
// v-model writes stay UI-local so AG-Grid state events don't re-fire
// the model output handler.
const scoresLocalState = ref(createPlDataTableStateV2());

// Spec R52 modal viewer. `pdbsMap` is {key, value: {handle}} pairs keyed
// by scClonotypeKey; `viewer` is set when a row's open-button fires and
// the slideover opens via `:model-value="viewer !== undefined"`.
const pdbsMap = computed(() => app.model.outputs.clonotypePdbsMap);
const clonotypeAxisId = computed(() => app.model.outputs.clonotypeAxisId);

// F2 pretty clonotype labels. The PFrame driver auto-joins upstream's
// `pl7.app/label` column into `scoresTable.fullPframeHandle` on the
// shared scClonotypeKey axis; resolving labels through that handle
// avoids a second result-pool query and stays in sync with the table.
const clonotypeLabelsPf = computed(
  () => pfHandleFrom(app.model.outputs.scoresTable) as PFrameHandle | undefined,
);
const { resolveLabel } = useClonotypeLabels(clonotypeLabelsPf, clonotypeAxisId);

// Dataset-level mode (uniform per R7) resolved from the per-clonotype
// `pl7.app/liabilities/mode` column and written back to BlockData so R51
// column visibility, R54 mode-specific histogram, and R55 subtitle all
// key off `app.model.data.detectedMode`.
const { mode: resolvedMode } = useDetectedMode(clonotypeLabelsPf);
watch(resolvedMode, (next) => {
  if (next && next !== app.model.data.detectedMode) {
    app.model.data.detectedMode = next;
  }
});

const selectedClonotypeKey = ref<string | null>(null);
const viewer = ref<PlStructureViewerProps>();

const scoresTableOutput = computed(() => app.model.outputs.scoresTable);

const { selectedClusterAssignment } = useClusterAssignments(
  scoresTableOutput,
  selectedClonotypeKey,
);
const { runSummary, showRedAlert, showGatedAlert } = useRunSummaryAlerts(scoresTableOutput);

// Settings auto-opens on first load when no input is configured.
const settingsOpen = ref(!app.model.data.dataset?.primary?.column);

// `PTableKey` is `[scClonotypeKey]`; look up the PDB handle in `pdbsMap`
// and seed the viewer props. Other modal contents (cluster badge, etc.)
// read `selectedClonotypeKey` so everything updates together.
function openViewerForRow(rowKey?: PTableKey) {
  const rawKey = rowKey?.at(0);
  if (rawKey == null) return;
  const key = String(rawKey);
  const handle = pdbsMap.value?.find((entry) => String(entry.key.at(0)) === key)?.value?.handle;
  if (!handle) return;
  selectedClonotypeKey.value = key;
  const label = resolveLabel(key) || key;
  viewer.value = { handle, fileName: `${label}.pdb` };
}

function handleViewerVisibility(open: boolean) {
  if (!open) {
    viewer.value = undefined;
    selectedClonotypeKey.value = null;
  }
}

const numberingSchemeOptions = [
  { value: "", label: "unknown (no region weighting)" },
  { value: "imgt", label: "IMGT" },
  { value: "chothia", label: "Chothia" },
  { value: "kabat", label: "Kabat" },
];

const modalTitle = computed(() => {
  const k = selectedClonotypeKey.value;
  return k ? `${resolveLabel(k)} · liabilities detail` : "Clonotype detail";
});
</script>

<template>
  <PlBlockPage title="3D Structure-Based Liabilities">
    <template #append>
      <PlBtnGhost @click.stop="() => (settingsOpen = true)">
        Settings
        <template #append>
          <PlMaskIcon24 name="settings" />
        </template>
      </PlBtnGhost>
    </template>

    <PlSlideModal v-model="settingsOpen" close-on-outside-click shadow>
      <template #title>Settings</template>

      <!-- Spec R1 / R46. `PlDatasetSelector` surfaces anchor-marked
           datasets from the result pool (3D Structure Prediction's
           `pdbsMap` since v1.0.11) with subset filters
           (`predictionSuccessful`, `confident`) auto-attached. v-model
           carries the full `{primary, enrichments?}` envelope; the model
           `.args()` unwraps `data.dataset.primary` back to the
           `PrimaryRef` the workflow already consumes. -->
      <PlDatasetSelector
        v-model="app.model.data.dataset"
        :options="app.model.outputs.datasetOptions"
        label="Predicted structures (from 3D Structure Prediction)"
        clearable
      />

      <div class="field-grid field-grid--settings">
        <PlDropdown
          v-model="app.model.data.numberingScheme"
          :options="numberingSchemeOptions"
          label="Numbering scheme"
        />
        <PlTextField
          v-model="app.model.data.heavyChainId"
          label="Heavy chain override"
          placeholder="auto from REMARK 99"
        />
        <PlTextField
          v-model="app.model.data.lightChainId"
          label="Light chain override"
          placeholder="auto from REMARK 99"
        />
      </div>
      <p class="help-text help-text--tight">
        Heavy / light chain letters are auto-detected from each PDB's
        <code>REMARK 99 PLATFORMA CDR*</code> records (spec R9, emitted by upstream IMGT-numbered
        ImmuneBuilder PDBs). Set the override fields to a single chain letter (e.g. <code>A</code>)
        only when REMARK 99 is absent and you need to manually map H / L.
      </p>

      <PlAccordionSection label="Advanced thresholds">
        <div class="field-grid">
          <PlNumberField
            v-model="app.model.data.frConfThresh"
            label="FR confidence threshold (Å, R34)"
            :minValue="1"
            :maxValue="10"
            :step="0.5"
          />
          <PlNumberField
            v-model="app.model.data.cdrConfThresh"
            label="CDR confidence threshold (Å, R34)"
            :minValue="1"
            :maxValue="12"
            :step="0.5"
          />
        </div>
        <p class="help-text">
          Defaults (4.0 / 6.0) are calibrated for ImmuneBuilder-predicted PDBs (R34). Raise the
          confidence thresholds when running on experimental crystal structures whose B-factors are
          Å² temperature factors rather than predicted error. rSASA cutoff is hardcoded at 0.075 per
          spec R12 (Raybould 2019 canonical).
        </p>
      </PlAccordionSection>
    </PlSlideModal>

    <!-- Empty-state CTA when no input is configured. Settings auto-opens
         on first load (see `settingsOpen` ref); this is for the case
         where the user closed the modal without picking a dataset. -->
    <div v-if="!app.model.data.dataset?.primary?.column" class="empty-state">
      <div class="empty-state__title">No predicted structures selected</div>
      <p class="empty-state__body">
        Pick a dataset from an upstream 3D Structure Prediction block in
        <strong>Settings</strong> (top-right). The block runs per clonotype and emits motif /
        cysteine / surface-metric PColumns plus the composite developability score.
      </p>
      <PlBtnGhost @click.stop="() => (settingsOpen = true)">
        Open Settings
        <template #append>
          <PlMaskIcon24 name="settings" />
        </template>
      </PlBtnGhost>
    </div>

    <!-- Spec R44 , run-summary alert: >10% of clonotypes have any red flag. -->
    <PlAlert
      v-if="showRedAlert && runSummary"
      class="run-alert"
      type="warn"
      label="Red-flag clonotypes exceed 10% (spec R44)"
      icon
    >
      {{ runSummary.redClonotypes }} of {{ runSummary.total }} clonotypes ({{
        Math.round(runSummary.redFraction * 100)
      }}%) carry at least one red Raybould threshold flag. Inspect the table below for which metrics
      are driving this.
    </PlAlert>
    <!-- Spec R45 , run-summary alert: >25% confidence-gated motifs. -->
    <PlAlert
      v-if="showGatedAlert && runSummary"
      class="run-alert"
      type="warn"
      label="Confidence-gated motifs exceed 25% (spec R45)"
      icon
    >
      {{ runSummary.gatedClonotypes }} of {{ runSummary.total }} clonotypes ({{
        Math.round(runSummary.gatedFraction * 100)
      }}%) have at least one motif gated by the per-residue confidence cutoff. Either ImmuneBuilder
      is uncertain about these regions or the gating thresholds (FR
      {{ app.model.data.frConfThresh }} Å / CDR {{ app.model.data.cdrConfThresh }} Å) are too tight
      for this dataset.
    </PlAlert>

    <!-- Spec R51 , primary view. One row per clonotype; default-visible
         columns set in `workflow/src/specs.lib.tengo` (mode, both risk
         classes, dev score, surfaced motif / extra-cys / broken-canonical
         counts, and the Raybould threshold flags). Raw metric values,
         motif risk score, low-confidence fractions, and totalCdrLength
         are hidden behind AG-Grid's "Columns" panel. The open button on
         the clonotype-axis cell fires `@cell-button-clicked`, which
         seeds the row's PDB handle into `viewer` and pops the modal. -->
    <div v-if="app.model.data.dataset?.primary?.column" class="scores-table">
      <PlAgDataTableV2
        v-model="scoresLocalState"
        :settings="scoresTableSettings"
        :show-cell-button-for-axis-id="clonotypeAxisId"
        :cell-button-invoke-rows-on-double-click="true"
        not-ready-text="Run on a predicted-structures dataset to see per-clonotype scores"
        no-rows-text="No scored clonotypes"
        @cell-button-clicked="openViewerForRow"
        @row-double-clicked="openViewerForRow"
      />
    </div>

    <!-- Spec R52 + R53 , viewer + per-clonotype detail panel in a
         slideover triggered by the row's open button. Closes by setting
         `viewer = undefined`, which also clears the clonotype selection
         so cluster badge / detail-panel content reset between opens. -->
    <PlSlideModal
      :model-value="viewer !== undefined"
      width="100%"
      :close-on-outside-click="false"
      @update:model-value="handleViewerVisibility"
    >
      <template #title>{{ modalTitle }}</template>

      <div v-if="viewer && selectedClusterAssignment" class="cluster-badge">
        <span class="cluster-badge__name"> Cluster {{ selectedClusterAssignment.clusterId }} </span>
        <span v-if="selectedClusterAssignment.isCentroid" class="cluster-badge__pill">
          CENTROID
        </span>
        <span
          v-else-if="selectedClusterAssignment.tmScoreToCentroid !== null"
          class="cluster-badge__tm"
        >
          TM-score to centroid {{ selectedClusterAssignment.tmScoreToCentroid.toFixed(3) }}
        </span>
      </div>

      <div v-if="viewer" class="viewer-frame">
        <PlStructureViewer v-bind="viewer" initial-color-scheme="uncertainty" />
      </div>
    </PlSlideModal>
  </PlBlockPage>
</template>

<style scoped>
.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}
.field-grid--settings {
  margin-top: 12px;
  margin-bottom: 4px;
}

.help-text {
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 12px;
}
.help-text--tight {
  margin-top: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  margin-top: 24px;
  background: rgba(148, 163, 184, 0.06);
  border: 1px dashed rgba(148, 163, 184, 0.4);
  border-radius: 8px;
  gap: 12px;
}
.empty-state__title {
  font-size: 15px;
  font-weight: 600;
  color: #374151;
}
.empty-state__body {
  font-size: 13px;
  color: #6b7280;
  text-align: center;
  max-width: 480px;
  margin: 0;
  line-height: 1.5;
}

.run-alert {
  margin-top: 12px;
}

.scores-table {
  margin-top: 12px;
  height: 720px;
}

.cluster-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  margin-bottom: 12px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 6px;
  font-size: 13px;
  color: #3730a3;
}
.cluster-badge__name {
  font-weight: 600;
}
.cluster-badge__pill {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 10px;
  background: #3730a322;
  color: #3730a3;
}
.cluster-badge__tm {
  color: #4f46e5;
  font-size: 12px;
}

.viewer-frame {
  height: 720px;
  display: flex;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}
</style>
