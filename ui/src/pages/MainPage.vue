<script setup lang="ts">
import type { PlStructureViewerProps } from "@milaboratories/structure-viewer";
import { PlStructureViewer } from "@milaboratories/structure-viewer";
import type { PFrameHandle, PTableKey } from "@platforma-sdk/model";
import { createPlDataTableStateV2 } from "@platforma-sdk/model";
import { defaultBlockLabelFor } from "@platforma-open/milaboratories.3d-structure-based-liabilities.model";
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDatasetSelector,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  PlTextField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref } from "vue";
import { useApp } from "../app";

import { useClonotypeLabels } from "../composables/useClonotypeLabels";
import { useClusterAssignments } from "../composables/useClusterAssignments";
import { useRunSummaryAlerts } from "../composables/useRunSummaryAlerts";
import { pfHandleFrom } from "../composables/ptableCell";

const app = useApp();

// `sourceId` is versioned so a shape change on the underlying PColumn
// invalidates AG-Grid's column-order cache.
const scoresTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.scoresTable,
  sourceId: () => "scores-v2",
});
// v-model writes stay UI-local so AG-Grid state events don't re-fire the
// model output handler.
const scoresLocalState = ref(createPlDataTableStateV2());

const pdbsMap = computed(() => app.model.outputs.clonotypePdbsMap);
const clonotypeAxisId = computed(() => app.model.outputs.clonotypeAxisId);

// Pretty clonotype labels resolved through the table's PFrame handle, which
// already auto-joins upstream's `pl7.app/label` column.
const clonotypeLabelsPf = computed(
  () => pfHandleFrom(app.model.outputs.scoresTable) as PFrameHandle | undefined,
);
const { resolveLabel } = useClonotypeLabels(clonotypeLabelsPf, clonotypeAxisId);

const selectedClonotypeKey = ref<string | null>(null);
const viewer = ref<PlStructureViewerProps>();

const scoresTableOutput = computed(() => app.model.outputs.scoresTable);

const { selectedClusterAssignment } = useClusterAssignments(
  scoresTableOutput,
  selectedClonotypeKey,
);
const { runSummary, showGatedAlert } = useRunSummaryAlerts(scoresTableOutput);

// Settings auto-opens on first load when no input is configured.
const settingsOpen = ref(!app.model.data.dataset?.primary?.column);

// Look up the row's PDB handle and seed the viewer props.
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

const modalTitle = computed(() => {
  const k = selectedClonotypeKey.value;
  return k ? `${resolveLabel(k)} · liabilities detail` : "Clonotype detail";
});
</script>

<template>
  <PlBlockPage
    v-model:subtitle="app.model.data.customBlockLabel"
    :subtitle-placeholder="defaultBlockLabelFor(app.model.data, app.model.outputs.detectedMode)"
    title="3D Structure-Based Liabilities"
  >
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

      <PlDatasetSelector
        v-model="app.model.data.dataset"
        :options="app.model.outputs.datasetOptions"
        label="3D Structures"
        clearable
      />

      <div class="field-grid field-grid--settings">
        <PlTextField
          v-model="app.model.data.heavyChainId"
          label="Heavy chain"
          placeholder="auto-detect"
        >
          <template #tooltip>
            Which chain in the structure is the heavy chain. Leave empty to detect it automatically;
            set a single chain letter (e.g. A) only if a structure has no chain annotation and
            detection fails.
          </template>
        </PlTextField>
        <PlTextField
          v-model="app.model.data.lightChainId"
          label="Light chain"
          placeholder="auto-detect"
        >
          <template #tooltip>
            Which chain in the structure is the light chain. Leave empty to detect it automatically;
            set a single chain letter only if detection fails.
          </template>
        </PlTextField>
      </div>

      <PlAccordionSection label="Advanced thresholds">
        <div class="field-grid">
          <PlNumberField
            v-model="app.model.data.frConfThresh"
            label="Framework confidence threshold (Å)"
            :minValue="1"
            :maxValue="10"
            :step="0.5"
          >
            <template #tooltip>
              Predicted-error cutoff above which framework-region motifs are treated as too
              uncertain to flag. Raise it for experimental crystal structures whose B-factors are
              temperature factors rather than predicted error.
            </template>
          </PlNumberField>
          <PlNumberField
            v-model="app.model.data.cdrConfThresh"
            label="CDR confidence threshold (Å)"
            :minValue="1"
            :maxValue="12"
            :step="0.5"
          >
            <template #tooltip>
              Same as the framework threshold, applied to the more flexible CDR loops, where
              predicted structures are typically less certain.
            </template>
          </PlNumberField>
        </div>
      </PlAccordionSection>
    </PlSlideModal>

    <PlAlert
      v-if="showGatedAlert && runSummary"
      class="run-alert"
      type="warn"
      label="More than 25% of motifs were confidence-gated"
      icon
    >
      {{ runSummary.gatedClonotypes }} of {{ runSummary.total }} clonotypes ({{
        Math.round(runSummary.gatedFraction * 100)
      }}%) have at least one motif gated by the per-residue confidence cutoff. Either the predicted
      structures are uncertain in these regions or the gating thresholds (FR
      {{ app.model.data.frConfThresh }} Å / CDR {{ app.model.data.cdrConfThresh }} Å) are too tight
      for this dataset.
    </PlAlert>

    <!-- One row per clonotype. The open button on the clonotype-key cell pops
         the structure-viewer modal for that row. -->
    <PlAgDataTableV2
      v-model="scoresLocalState"
      :settings="scoresTableSettings"
      :show-cell-button-for-axis-id="clonotypeAxisId"
      :cell-button-invoke-rows-on-double-click="true"
      :show-export-button="true"
      not-ready-text="Run on a 3D structures dataset to see per-clonotype scores"
      no-rows-text="No scored clonotypes"
      @cell-button-clicked="openViewerForRow"
      @row-double-clicked="openViewerForRow"
    />

    <PlSlideModal
      :model-value="viewer !== undefined"
      width="100%"
      :close-on-outside-click="false"
      @update:model-value="handleViewerVisibility"
    >
      <template #title>{{ modalTitle }}</template>

      <div v-if="viewer && selectedClusterAssignment" class="cluster-badge">
        <span class="cluster-badge__name"> Cluster {{ selectedClusterAssignment.clusterId }} </span>
        <span v-if="selectedClusterAssignment.isCentroid" class="cluster-badge__pill"
          >CENTROID</span
        >
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
}

.run-alert {
  margin-top: 12px;
}

.cluster-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  margin-bottom: 12px;
  border: 1px solid var(--border-color-default, rgba(99, 102, 241, 0.25));
  border-radius: 6px;
}
.cluster-badge__name {
  font-weight: 600;
}
.cluster-badge__pill {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 10px;
  border: 1px solid var(--border-color-default, rgba(99, 102, 241, 0.25));
}

.viewer-frame {
  height: 720px;
  display: flex;
  padding: 12px;
  border: 1px solid var(--border-color-default, #e5e7eb);
  border-radius: 6px;
}
</style>
