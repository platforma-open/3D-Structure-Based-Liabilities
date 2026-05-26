<script setup lang="ts">
import type { PlStructureViewerProps } from "@milaboratories/structure-viewer";
import { PlStructureViewer } from "@milaboratories/structure-viewer";
import type { PlRef, PTableKey } from "@platforma-sdk/model";
import { createPlDataTableStateV2, createPrimaryRef } from "@platforma-sdk/model";
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlDropdown,
  PlDropdownRef,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  PlTextField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watch } from "vue";
import { useApp } from "../app";

import ClonotypeDetailPanel from "../components/ClonotypeDetailPanel.vue";
import RiskSummaryBar from "../components/RiskSummaryBar.vue";
import { useClonotypeDetailFetch } from "../composables/useClonotypeDetailFetch";
import { useClonotypeLabels } from "../composables/useClonotypeLabels";
import { useDetectedMode } from "../composables/useDetectedMode";
import { useClusterAssignments } from "../composables/useClusterAssignments";
import { useRunSummaryAlerts } from "../composables/useRunSummaryAlerts";

const app = useApp();

// Spec R51 , per-clonotype scoresTable is now the primary view. The
// previous tab UI (table ↔ inline viewer) has been replaced by a row-
// click `PlSlideModal`, matching the pattern used in the upstream
// 3D-Structure-Prediction block. Cluster / centroid filtering happens
// through PlAgDataTable's own column filters , the standalone toggle
// is gone.
const scoresTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.scoresTable,
  sourceId: () => "scores-v2",
});
// v-model writes stay UI-local so AG-Grid state events don't re-fire the
// model output handler. Keeps the table out of placeholder-state limbo.
const scoresLocalState = ref(createPlDataTableStateV2());

// Spec R52 + R53 , modal-on-row-click. `clonotypePdbsMap` /
// `clonotypeJsonsMap` are {key, value: {handle}} pairs keyed by
// scClonotypeKey. `viewer` is set when a row's open-button fires; the
// modal opens via `:model-value="viewer !== undefined"`.
//
// Color schemes (by-confidence / by-rsasa / by-hydrophobicity per spec)
// are still blocked on `@milaboratories/structure-viewer` ≥ 0.3.0
// publish , PlStructureViewer renders Mol*'s default preset for now.
const pdbsMap = computed(() => app.model.outputs.clonotypePdbsMap);
const jsonsMap = computed(() => app.model.outputs.clonotypeJsonsMap);
const clonotypeAxisId = computed(() => app.model.outputs.clonotypeAxisId);

// F2 , pretty clonotype labels from the upstream `pl7.app/label` column.
// Used for the modal title, viewer file name, and detail-panel header.
// Source from scoresTable.fullPframeHandle (auto-joined label column);
// the standalone clonotypeLabelsPf output uses resultPool.findDataWithCompatibleSpec
// which returns empty for domain-bound axes.
// PlAgDataTable handles label substitution inside the table itself.
const clonotypeLabelsPf = computed(() => {
  const t = app.model.outputs.scoresTable;
  return t && t.ok ? t.value.fullPframeHandle : undefined;
});
const { resolveLabel } = useClonotypeLabels(clonotypeLabelsPf, clonotypeAxisId);

// Dataset-level mode (uniform per R7). Spec BlockData definition places
// detectedMode on `BlockData.detectedMode`; the model can't read PColumn
// data synchronously in an output callback, so the UI resolves it from
// the per-clonotype `pl7.app/liabilities/mode` column and writes back
// into BlockData on change. R51, R54, R55 read from `app.model.data.detectedMode`.
const { mode: resolvedMode } = useDetectedMode(clonotypeLabelsPf);
watch(resolvedMode, (next) => {
  if (next && next !== app.model.data.detectedMode) {
    app.model.data.detectedMode = next;
  }
});

const selectedClonotypeKey = ref<string | null>(null);
const viewer = ref<PlStructureViewerProps>();

const scoresTableOutput = computed(() => app.model.outputs.scoresTable);

const { clusterMap, selectedClusterAssignment } = useClusterAssignments(
  scoresTableOutput,
  selectedClonotypeKey,
);
const { detailReport } = useClonotypeDetailFetch(selectedClonotypeKey, jsonsMap);
const { runSummary, showRedAlert, showGatedAlert } = useRunSummaryAlerts(scoresTableOutput);

// Settings slide-over (predicted structures dropdown + numbering scheme
// override + chain mapping override + Advanced thresholds + hydrophobicity
// scale). Auto-opens on first load when no input is configured so new
// users land on the input form instead of an empty page.
const settingsOpen = ref(!app.model.data.primaryRef?.column);

// Spec R1 , `PrimaryRef` is a frozen `{__isPrimaryRef, column, filter?}`
// envelope. `PlDropdownRef` deals in plain `PlRef`, so we expose the
// inner `column` to the dropdown and rebuild the envelope on every
// change via `createPrimaryRef`. The filter slot (R47) stays
// `undefined` until subset selection is wired.
const primaryRefColumn = computed<PlRef | undefined>({
  get: () => app.model.data.primaryRef?.column,
  set: (value) => {
    app.model.data.primaryRef = value ? createPrimaryRef(value) : undefined;
  },
});

// Row-click handler , fired by `PlAgDataTableV2`'s `@cell-button-clicked`
// when the user hits the open button on the clonotype-axis cell. The key
// comes through as the first element of `PTableKey`; we then look up the
// PDB handle in `pdbsMap` and seed the viewer props (the slideover binds
// to `viewer !== undefined`). The detail panel + cluster badge read the
// same `selectedClonotypeKey` ref so everything in the modal updates
// together.
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

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const numberingSchemeOptions = [
  { value: "", label: ", unknown (no region weighting) ," },
  { value: "imgt", label: "IMGT" },
  { value: "chothia", label: "Chothia" },
  { value: "kabat", label: "Kabat" },
];

// R48 , selectable hydrophobicity scales for PSH. KD is the Raybould 2019
// default; the rest are the spec's calibration set (Raybould refs 31-35
// plus Black-Mould for the Gordon TNP comparison).
const hydrophobicityScaleOptions = [
  { value: "kd", label: "Kyte-Doolittle (default)" },
  { value: "ww", label: "Wimley-White (interface)" },
  { value: "hessa", label: "Hessa (biological)" },
  { value: "em", label: "Eisenberg-McLachlan (consensus)" },
  { value: "bm", label: "Black-Mould (normalized)" },
];

const modalTitle = computed(() => {
  const k = selectedClonotypeKey.value;
  if (!k) return "Clonotype detail";
  const label = resolveLabel(k);
  return label && label !== k ? `${label} · liabilities detail` : `${k} · liabilities detail`;
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

      <PlDropdownRef
        v-model="primaryRefColumn"
        :options="app.model.outputs.pdbOptions ?? []"
        label="Predicted structures (from 3D Structure Prediction)"
        clearable
      />

      <div
        :style="{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '12px',
          marginTop: '12px',
          marginBottom: '4px',
        }"
      >
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
      <p :style="{ fontSize: '12px', color: '#6b7280', marginTop: '0', marginBottom: '12px' }">
        Heavy / light chain letters are auto-detected from each PDB's
        <code>REMARK 99 PLATFORMA CDR*</code> records (spec R9, emitted by upstream IMGT-numbered
        ImmuneBuilder PDBs). Set the override fields to a single chain letter (e.g. <code>A</code>)
        only when REMARK 99 is absent and you need to manually map H / L.
      </p>

      <PlAccordionSection label="Advanced thresholds">
        <div
          :style="{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '12px',
            marginBottom: '8px',
          }"
        >
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
        <p :style="{ fontSize: '12px', color: '#6b7280', margin: '0 0 12px' }">
          Defaults (4.0 / 6.0) are calibrated for ImmuneBuilder-predicted PDBs (R34). Raise the
          confidence thresholds when running on experimental crystal structures whose B-factors are
          Å² temperature factors rather than predicted error. rSASA cutoff is hardcoded at 0.075 per
          spec R12 (Raybould 2019 canonical).
        </p>
        <div :style="{ marginBottom: '8px' }">
          <PlDropdown
            v-model="app.model.data.hydrophobicityScale"
            :options="hydrophobicityScaleOptions"
            label="Hydrophobicity scale (R48)"
          />
        </div>
        <p :style="{ fontSize: '12px', color: '#6b7280', margin: '0 0 12px' }">
          PSH weights each residue by its hydrophobicity (R25). Kyte-Doolittle is Raybould 2019's
          choice; switching scales lets you cross-check PSH and reproduce the spec's R48 sensitivity
          analysis. All scales are min-max normalized to [1.0, 2.0] so PSH magnitudes stay in the
          same ballpark, but relative ordering between residues changes , expect different
          red/amber/green calls near the threshold.
        </p>
      </PlAccordionSection>
    </PlSlideModal>

    <!-- Empty-state CTA when no input is configured. Settings auto-opens
         on first load (see `settingsOpen` ref); this is for the case
         where the user closed the modal without picking a dataset. -->
    <div
      v-if="!app.model.data.primaryRef?.column"
      :style="{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        marginTop: '24px',
        background: 'rgba(148, 163, 184, 0.06)',
        border: '1px dashed rgba(148, 163, 184, 0.4)',
        borderRadius: '8px',
        gap: '12px',
      }"
    >
      <div :style="{ fontSize: '15px', fontWeight: 600, color: '#374151' }">
        No predicted structures selected
      </div>
      <p
        :style="{
          fontSize: '13px',
          color: '#6b7280',
          textAlign: 'center',
          maxWidth: '480px',
          margin: '0',
          lineHeight: '1.5',
        }"
      >
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
      type="warn"
      label="Red-flag clonotypes exceed 10% (spec R44)"
      icon
      :style="{ marginTop: '12px' }"
    >
      {{ runSummary.redClonotypes }} of {{ runSummary.total }} clonotypes ({{
        pct(runSummary.redFraction)
      }}) carry at least one red Raybould threshold flag. Inspect the table below for which metrics
      are driving this.
    </PlAlert>
    <!-- Spec R45 , run-summary alert: >25% confidence-gated motifs. -->
    <PlAlert
      v-if="showGatedAlert && runSummary"
      type="warn"
      label="Confidence-gated motifs exceed 25% (spec R45)"
      icon
      :style="{ marginTop: '12px' }"
    >
      {{ runSummary.gatedClonotypes }} of {{ runSummary.total }} clonotypes ({{
        pct(runSummary.gatedFraction)
      }}) have at least one motif gated by the per-residue confidence cutoff. Either ImmuneBuilder
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
    <div v-if="app.model.data.primaryRef?.column" :style="{ marginTop: '12px', height: '720px' }">
      <PlAgDataTableV2
        v-model="scoresLocalState"
        :settings="scoresTableSettings"
        :show-cell-button-for-axis-id="clonotypeAxisId"
        :cell-button-invoke-rows-on-double-click="false"
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

      <RiskSummaryBar v-if="viewer" :report="detailReport" />

      <!-- R42 cluster info badge , renders only when the 3D Structure
           Clustering block is upstream and the selected clonotype has
           an assignment in clusterMap. -->
      <div
        v-if="viewer && selectedClusterAssignment"
        :style="{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '6px 12px',
          marginBottom: '12px',
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.25)',
          borderRadius: '6px',
          fontSize: '13px',
          color: '#3730a3',
        }"
      >
        <span :style="{ fontWeight: '600' }">
          Cluster {{ selectedClusterAssignment.clusterId }}
        </span>
        <span
          v-if="selectedClusterAssignment.isCentroid"
          :style="{
            fontSize: '11px',
            fontWeight: 600,
            padding: '1px 8px',
            borderRadius: '10px',
            background: '#3730a322',
            color: '#3730a3',
          }"
        >
          CENTROID
        </span>
        <span
          v-else-if="selectedClusterAssignment.tmScoreToCentroid !== null"
          :style="{ color: '#4f46e5', fontSize: '12px' }"
        >
          TM-score to centroid {{ selectedClusterAssignment.tmScoreToCentroid.toFixed(3) }}
        </span>
      </div>

      <div
        v-if="viewer"
        :style="{
          display: 'flex',
          alignItems: 'flex-start',
          border: '1px solid #e5e7eb',
          borderRadius: '6px',
          background: '#fff',
        }"
      >
        <div
          :style="{
            flex: '1 1 auto',
            minWidth: '0',
            height: '720px',
            display: 'flex',
            padding: '12px 12px 8px',
          }"
        >
          <PlStructureViewer v-bind="viewer" initial-color-scheme="uncertainty" />
        </div>
        <div :style="{ flex: '0 0 520px', minWidth: '480px', maxWidth: '620px' }">
          <ClonotypeDetailPanel
            v-if="selectedClonotypeKey"
            :report="detailReport"
            :clonotype-key="selectedClonotypeKey"
            :clonotype-label="resolveLabel(selectedClonotypeKey)"
          />
        </div>
      </div>
    </PlSlideModal>
  </PlBlockPage>
</template>
