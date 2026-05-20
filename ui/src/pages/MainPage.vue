<script setup lang="ts">
import type { PlStructureViewerProps } from "@milaboratories/structure-viewer";
import { PlStructureViewer } from "@milaboratories/structure-viewer";
import { createPlDataTableStateV2 } from "@platforma-sdk/model";
import {
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlBtnGhost,
  PlCheckbox,
  PlDropdown,
  PlDropdownRef,
  PlMaskIcon24,
  PlNumberField,
  PlSlideModal,
  PlTabs,
  PlTextField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watchEffect } from "vue";
import { useApp } from "../app";

import ClonotypeDetailPanel from "../components/ClonotypeDetailPanel.vue";
import RiskSummaryBar from "../components/RiskSummaryBar.vue";
import { useClonotypeDetailFetch } from "../composables/useClonotypeDetailFetch";
import { useClusterAssignments } from "../composables/useClusterAssignments";
import { useRunSummaryAlerts } from "../composables/useRunSummaryAlerts";

const app = useApp();

// Spec R51 — per-clonotype scalar metrics table.
// `scoresData` PFrame is only emitted on the PrimaryRef path; on the
// legacy single-PDB path `app.model.outputs.scoresTable` resolves to
// undefined and `usePlDataTableSettingsV2` keeps the grid in its
// `not-ready` overlay state. No special-casing required here.
const scoresTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.scoresTable,
  sourceId: () => "scores-v1",
});
// Scores table's v-model writes are kept UI-local (not echoed back to
// `app.model.data.scoresTableState`) so the model output handler doesn't
// re-fire on every grid state event. Motifs and cysteines live on their
// own routes — see app.ts. Putting all three tables on one page caused
// AG-Grid to stick in placeholder state (header rendered, body collapsed).
const scoresLocalState = ref(createPlDataTableStateV2());

// Spec R52 + R53 — inline viewer + per-clonotype detail panel below the
// scoresTable. `clonotypePdbsMap` / `clonotypeJsonsMap` are
// {key, value: {handle}} pairs keyed by scClonotypeKey. We auto-pick the
// first clonotype on load; a small dropdown lets the user switch.
//
// Color schemes (by-confidence / by-rsasa / by-hydrophobicity per spec)
// are not yet supported — PlStructureViewer renders Mol*'s default preset
// (cartoon, by chain). Documented gap in progression.md (R52 row).
const pdbsMap = computed(() => app.model.outputs.clonotypePdbsMap);
const jsonsMap = computed(() => app.model.outputs.clonotypeJsonsMap);

const selectedClonotypeKey = ref<string | null>(null);
const centroidsOnly = ref(false);

const scoresTableOutput = computed(() => app.model.outputs.scoresTable);

// Spec R42 cluster wiring + R53 per-clonotype JSON fetch + R44/R45 alert
// computation all live as composables — keeps MainPage's script readable
// and makes the async race-guard logic reusable / testable in isolation.
const { clusterMap, hasClusterData, selectedClusterAssignment } = useClusterAssignments(
  scoresTableOutput,
  selectedClonotypeKey,
  centroidsOnly,
);
const { detailReport } = useClonotypeDetailFetch(selectedClonotypeKey, jsonsMap);
const { runSummary, showRedAlert, showGatedAlert } = useRunSummaryAlerts(scoresTableOutput);

// Tab between the 3D viewer + detail panel and the per-clonotype
// scoresTable. Default to the visualisation — the table is the bulk
// overview, the visualisation is the deep-dive readout per spec R52/R53.
const activeView = ref<"viewer" | "table">("viewer");

// Settings slide-over (predicted structures dropdown + numbering scheme
// override + chain mapping override + Advanced thresholds + hydrophobicity
// scale). Auto-opens on first load when no input is configured so new
// users land on the input form instead of an empty page.
const settingsOpen = ref(!app.model.data.pdbRef);
const viewTabOptions = [
  { value: "viewer" as const, label: "3D structure + detail" },
  { value: "table" as const, label: "Per-clonotype table" },
];

// Auto-select the first available clonotype as soon as the PDB map
// arrives; reset when the input shape changes so we don't dangle on a
// stale key. The user can override via the dropdown.
watchEffect(() => {
  const entries = pdbsMap.value;
  if (!entries || entries.length === 0) {
    selectedClonotypeKey.value = null;
    return;
  }
  const current = selectedClonotypeKey.value;
  if (!current || !entries.some((e) => String(e.key.at(0)) === current)) {
    selectedClonotypeKey.value = String(entries[0].key.at(0));
  }
});

const viewerProps = computed<PlStructureViewerProps | null>(() => {
  const key = selectedClonotypeKey.value;
  if (!key) return null;
  const handle = pdbsMap.value?.find((e) => String(e.key.at(0)) === key)?.value?.handle;
  if (!handle) return null;
  return { handle, fileName: `${key}.pdb` };
});

const clonotypeOptions = computed(() => {
  const entries = pdbsMap.value ?? [];
  const cmap = clusterMap.value;
  const filtered = centroidsOnly.value
    ? entries.filter((e) => cmap[String(e.key.at(0))]?.isCentroid)
    : entries;
  return filtered.map((e) => {
    const k = String(e.key.at(0));
    const assignment = cmap[k];
    const label = assignment
      ? `${k} · cluster ${assignment.clusterId}${assignment.isCentroid ? " ★" : ""}`
      : k;
    return { value: k, label };
  });
});

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const numberingSchemeOptions = [
  { value: "", label: "— unknown (no region weighting) —" },
  { value: "imgt", label: "IMGT" },
  { value: "chothia", label: "Chothia" },
  { value: "kabat", label: "Kabat" },
];

// R48 — selectable hydrophobicity scales for PSH. KD is the Raybould 2019
// default; the rest are the spec's calibration set (Raybould refs 31–35
// plus Black-Mould for the Gordon TNP comparison).
const hydrophobicityScaleOptions = [
  { value: "kd", label: "Kyte-Doolittle (default)" },
  { value: "ww", label: "Wimley-White (interface)" },
  { value: "hessa", label: "Hessa (biological)" },
  { value: "em", label: "Eisenberg-McLachlan (consensus)" },
  { value: "bm", label: "Black-Mould (normalized)" },
];
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
        v-model="app.model.data.pdbRef"
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
            v-model="app.model.data.rsasaBuriedCutoff"
            label="rSASA buried cutoff (R12)"
            :minValue="0"
            :maxValue="1"
            :step="0.005"
          />
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
          Defaults (0.075 / 4.0 / 6.0) are calibrated for ImmuneBuilder-predicted PDBs (R34). Raise
          the confidence thresholds when running on experimental crystal structures whose B-factors
          are Å² temperature factors rather than predicted error.
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
          same ballpark, but relative ordering between residues changes — expect different
          red/amber/green calls near the threshold.
        </p>
      </PlAccordionSection>
    </PlSlideModal>

    <!-- Spec R44 — run-summary alert: >10% of clonotypes have any red flag. -->
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
    <!-- Spec R45 — run-summary alert: >25% confidence-gated motifs. -->
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

    <!-- Spec R51 (table) + R52 / R53 (viewer + detail) — same data,
         different framing. Defaults to the visualisation; switching to
         the table gives the bulk-overview view per R51. -->
    <div :style="{ marginTop: '12px', marginBottom: '16px' }">
      <div
        :style="{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: '12px',
          borderBottom: '1px solid #e5e7eb',
          marginBottom: '12px',
        }"
      >
        <PlTabs v-model="activeView" :options="viewTabOptions" />
        <div
          :style="{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            paddingBottom: '8px',
            flexWrap: 'wrap',
          }"
        >
          <PlCheckbox v-if="activeView === 'viewer' && hasClusterData" v-model="centroidsOnly">
            Centroids only
          </PlCheckbox>
          <div :style="{ minWidth: '260px' }">
            <PlDropdown
              v-if="activeView === 'viewer' && clonotypeOptions.length > 1"
              :model-value="selectedClonotypeKey ?? ''"
              :options="clonotypeOptions"
              label="Clonotype"
              @update:model-value="(v) => (selectedClonotypeKey = v ? String(v) : null)"
            />
          </div>
        </div>
      </div>

      <div v-show="activeView === 'viewer'" :style="{ paddingTop: '12px' }">
        <RiskSummaryBar v-if="viewerProps" :report="detailReport" />

        <!-- R42 cluster info badge. Only renders when the 3D Structure
             Clustering block is upstream and the selected clonotype has
             an assignment in clusterMap. -->
        <div
          v-if="viewerProps && selectedClusterAssignment"
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
          v-if="viewerProps"
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
              position: 'sticky',
              top: '0',
            }"
          >
            <PlStructureViewer v-bind="viewerProps" />
          </div>
          <div :style="{ flex: '0 0 400px', minWidth: '380px', maxWidth: '440px' }">
            <ClonotypeDetailPanel
              v-if="selectedClonotypeKey"
              :report="detailReport"
              :clonotype-key="selectedClonotypeKey"
            />
          </div>
        </div>
        <p v-else :style="{ fontSize: '13px', color: '#6b7280', padding: '24px 4px' }">
          Run on a predicted-structures dataset to see the 3D viewer + per-clonotype detail.
        </p>
      </div>

      <div v-show="activeView === 'table'" :style="{ paddingTop: '12px' }">
        <p :style="{ fontSize: '12px', color: '#6b7280', margin: '0 0 8px' }">
          One row per clonotype. Default view shows mode, both risk classes, the composite
          developability score, surfaced motif / exposed extra cys / broken canonical disulfide
          counts, and the Raybould threshold flags (R39, R41a). Raw metric values, motif risk score,
          low-confidence fractions, and totalCdrLength are hidden behind "Columns".
        </p>
        <div :style="{ height: '480px' }">
          <PlAgDataTableV2
            v-model="scoresLocalState"
            :settings="scoresTableSettings"
            not-ready-text="Run on a predicted-structures dataset to see per-clonotype scores"
            no-rows-text="No scored clonotypes"
          />
        </div>
      </div>
    </div>
  </PlBlockPage>
</template>
