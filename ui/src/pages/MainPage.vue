<script setup lang="ts">
import type { LiabilitiesReport } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import {
  createPlDataTableStateV2,
  getRawPlatformaInstance,
  type PlRef,
} from "@platforma-sdk/model";
import {
  computedResult,
  PlAccordionSection,
  PlAgDataTableV2,
  PlAlert,
  PlBlockPage,
  PlDropdown,
  PlDropdownRef,
  PlFileInput,
  PlNumberField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed, ref, watchEffect } from "vue";
import { useApp } from "../app";

import PdbLiabilityMap from "../components/pdb/PdbLiabilityMap.vue";

// Spec R12 — Raybould 2019 canonical cutoff. rSASA below this is "buried".
const BURIED_CUTOFF = 0.075;

const app = useApp();
// `liabilitiesJson` is only emitted on the legacy single-PDB upload path.
// On the PrimaryRef path the workflow produces a per-clonotype File
// ResourceMap instead, so this output is absent — `computedResult` returns
// an unsettled / error result and `report` stays null (which hides the
// single-structure stats panel + residue map below).
const liabilitiesJson = computedResult(() => app.model.outputs.liabilitiesJson);

const report = computed<LiabilitiesReport | null>(() => {
  try {
    const text = liabilitiesJson.value?.value;
    return text ? (JSON.parse(text) as LiabilitiesReport) : null;
  } catch {
    return null;
  }
});

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

// Spec R44 / R45 run-summary alerts.
// Reads the *Flag columns + confidenceGatedMotifCount from the scores PTable
// (3 rows on the live dataset, so this is a cheap fetch) and surfaces a
// banner when:
//   R44: > 10 % of clonotypes have at least one red metric flag
//   R45: > 25 % of clonotypes have ≥ 1 confidence-gated motif
const RED = "red";
const FLAG_COL_NAMES = new Set([
  "pl7.app/liabilities/totalCdrLengthFlag",
  "pl7.app/liabilities/pshFlag",
  "pl7.app/liabilities/ppcFlag",
  "pl7.app/liabilities/pncFlag",
  "pl7.app/liabilities/sfvcspFlag",
  "pl7.app/liabilities/cdrh3CompactnessFlag",
]);
const GATED_COL_NAME = "pl7.app/liabilities/confidenceGatedMotifCount";

type RunSummary = {
  total: number;
  redClonotypes: number;
  gatedClonotypes: number;
  redFraction: number;
  gatedFraction: number;
};
const runSummary = ref<RunSummary | null>(null);

// Pull *Flag + confidenceGated values from the scoresTable PTable and compute
// the alert fractions. watchEffect captures the reactive deps on the
// `tableOutput.value.fullTableHandle` access — anything before the first
// `await` re-runs the effect when the model output changes.
watchEffect(async () => {
  const tableOutput = app.model.outputs.scoresTable;
  if (!tableOutput?.ok || !tableOutput.value?.fullTableHandle) {
    runSummary.value = null;
    return;
  }
  const handle = tableOutput.value.fullTableHandle;
  const pf = getRawPlatformaInstance().pFrameDriver;

  const shape = await pf.getShape(handle);
  if (shape.rows === 0) {
    runSummary.value = null;
    return;
  }
  const spec = await pf.getSpec(handle);
  const flagIndices: number[] = [];
  let gatedIndex = -1;
  for (let i = 0; i < spec.length; i++) {
    const name = spec[i]?.spec?.name;
    if (!name) continue;
    if (FLAG_COL_NAMES.has(name)) flagIndices.push(i);
    if (name === GATED_COL_NAME) gatedIndex = i;
  }
  if (flagIndices.length === 0 && gatedIndex === -1) {
    runSummary.value = null;
    return;
  }

  const requestIndices = [...flagIndices, gatedIndex].filter((i) => i >= 0);
  const data = await pf.getData(handle, requestIndices, { offset: 0, length: shape.rows });
  const rowCount = shape.rows;

  let redClonotypes = 0;
  for (let row = 0; row < rowCount; row++) {
    for (let k = 0; k < flagIndices.length; k++) {
      const col = data[k];
      const value = Array.isArray(col?.data) ? col.data[row] : undefined;
      if (value === RED) {
        redClonotypes++;
        break;
      }
    }
  }

  let gatedClonotypes = 0;
  if (gatedIndex !== -1) {
    // Long columns come back from pfDriver as a numeric-key wrapped object
    // carrying BigInts (e.g. `{ 0: 12n, 1: 35n }`). Cast through `unknown`
    // because PVectorData* is a union of TypedArrays / arrays / wrapped maps.
    const col = data[flagIndices.length];
    const get = (i: number): number => {
      const d = col?.data as unknown;
      if (Array.isArray(d)) return Number((d as unknown[])[i] ?? 0);
      if (d && typeof d === "object") {
        const v = (d as Record<string, unknown>)[String(i)];
        return v === undefined ? 0 : Number(v);
      }
      return 0;
    };
    for (let row = 0; row < rowCount; row++) {
      if (get(row) > 0) gatedClonotypes++;
    }
  }

  runSummary.value = {
    total: rowCount,
    redClonotypes,
    gatedClonotypes,
    redFraction: redClonotypes / rowCount,
    gatedFraction: gatedClonotypes / rowCount,
  };
});

const RED_FLAG_THRESHOLD = 0.1;
const GATED_THRESHOLD = 0.25;
const showRedAlert = computed(() => (runSummary.value?.redFraction ?? 0) > RED_FLAG_THRESHOLD);
const showGatedAlert = computed(() => (runSummary.value?.gatedFraction ?? 0) > GATED_THRESHOLD);
function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const mode = computed(() => report.value?.mode ?? "empty");
const surfacedMotifCount = computed(() => report.value?.scores?.surfacedMotifCount ?? 0);
const confidenceGatedMotifCount = computed(
  () => report.value?.scores?.confidenceGatedMotifCount ?? 0,
);
const motifStructuralRiskScore = computed(
  () => report.value?.scores?.motifStructuralRiskScore ?? 0,
);
const surfaceMetrics = computed(() => {
  const m = report.value?.surfaceMetrics;
  if (!m || !("mode" in m)) return null;
  return m;
});
const developabilityScore = computed(
  () => report.value?.scores?.structuralDevelopabilityScore ?? 0,
);
const developabilityRisk = computed(
  () => report.value?.scores?.structuralDevelopabilityRisk ?? "None",
);
const integrityRisk = computed(() => report.value?.scores?.structuralIntegrityRisk ?? "None");
function fmtLowConf(value: number | null | undefined): string {
  if (value == null) return "";
  return ` (${Math.round(value * 100)}% low-conf)`;
}
const RISK_COLOR: Record<string, string> = {
  None: "#65a30d",
  Low: "#84cc16",
  Medium: "#d97706",
  High: "#dc2626",
  Present: "#dc2626",
};

const numberingSchemeOptions = [
  { value: "", label: "— unknown (no region weighting) —" },
  { value: "imgt", label: "IMGT" },
  { value: "chothia", label: "Chothia" },
  { value: "kabat", label: "Kabat" },
];

// Heavy / light chain dropdowns offer the chain IDs from the loaded PDB plus
// a "none" option (so antigen chains can be left untagged).
// When the user picks an upstream PDBs dataset, drop the legacy file upload
// (the two inputs are mutually exclusive) and force numberingScheme to IMGT —
// that's the domain the upstream column carries.
function onPdbRefUpdate(ref: PlRef | undefined) {
  if (ref) {
    app.model.data.pdb = undefined;
    if (!app.model.data.numberingScheme) {
      app.model.data.numberingScheme = "imgt";
    }
  }
}

const chainOptions = computed(() => {
  const opts: { value: string; label: string }[] = [{ value: "", label: "— none —" }];
  if (!report.value) return opts;
  for (const c of report.value.chains) {
    opts.push({ value: c.id, label: `${c.id} (${c.residues.length} residues)` });
  }
  return opts;
});
</script>

<template>
  <PlBlockPage title="3D Structure-Based Liabilities">
    <PlDropdownRef
      v-model="app.model.data.pdbRef"
      :options="app.model.outputs.pdbOptions ?? []"
      label="Predicted structures (from 3D Structure Prediction)"
      clearable
      @update:model-value="onPdbRefUpdate"
    />
    <p
      v-if="!app.model.data.pdbRef"
      :style="{ fontSize: '12px', color: '#6b7280', margin: '6px 0 12px' }"
    >
      Or upload a single PDB file (dev / single-structure workflow):
    </p>
    <PlFileInput
      v-if="!app.model.data.pdbRef"
      v-model="app.model.data.pdb"
      label="PDB file"
      :extensions="['.pdb']"
      placeholder="Drop a .pdb file"
      clearable
    />

    <div
      :style="{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
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
      <PlDropdown
        v-model="app.model.data.heavyChainId"
        :options="chainOptions"
        label="Heavy chain"
      />
      <PlDropdown
        v-model="app.model.data.lightChainId"
        :options="chainOptions"
        label="Light chain"
      />
    </div>
    <p :style="{ fontSize: '12px', color: '#6b7280', marginTop: '0', marginBottom: '12px' }">
      Region weighting (R19) on motif scores is applied only when a scheme and at least one of
      heavy/light is set. Antigen chains (and any chain not mapped to H or L) get
      <code>region = "-"</code> and the neutral weight.
    </p>

    <PlAccordionSection label="Advanced thresholds">
      <div
        :style="{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
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
    </PlAccordionSection>

    <div v-if="report">
      <p
        v-if="app.model.data.pdbRef"
        :style="{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }"
      >
        Note: stats panel + residue map below are populated from a single liabilities.json. On the
        predicted-structures path each clonotype has its own report — multi-clonotype stats /
        per-row drill-down is the next UI slice. The motif and cysteine tables already show all
        clonotypes.
      </p>
      <table
        :style="{
          fontSize: '15px',
          color: '#374151',
          background: 'rgba(148, 163, 184, 0.08)',
          border: '1px solid rgba(148, 163, 184, 0.25)',
          borderRadius: '4px',
          padding: '4px',
          marginBottom: '16px',
          borderCollapse: 'separate',
          borderSpacing: '0',
        }"
      >
        <tbody>
          <tr :title="`Spec R7 — auto-detected from chain count`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              Mode (R7)
            </td>
            <td :style="{ padding: '8px 12px' }">{{ mode }}</td>
          </tr>
          <tr :title="`Spec R38 — surfacedMotifCount, confidenceGatedMotifCount`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              Surface-exposed motifs
            </td>
            <td :style="{ padding: '8px 12px' }">
              {{ surfacedMotifCount }}
              <span :style="{ color: '#6b7280' }">
                ({{ confidenceGatedMotifCount }} confidence-gated)
              </span>
            </td>
          </tr>
          <tr :title="`Sum of non-gated motif weightedScore (spec R20)`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              motifStructuralRiskScore
            </td>
            <td :style="{ padding: '8px 12px' }">{{ motifStructuralRiskScore.toFixed(1) }}</td>
          </tr>
          <tr :title="`Spec R41 — motif + flag + Cys contributions`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              structuralDevelopabilityScore
            </td>
            <td :style="{ padding: '8px 12px' }">{{ developabilityScore.toFixed(1) }}</td>
          </tr>
          <tr :title="`Spec R41a — over fixable items`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              structuralDevelopabilityRisk
            </td>
            <td :style="{ padding: '8px 12px' }">
              <b :style="{ color: RISK_COLOR[developabilityRisk] }">{{ developabilityRisk }}</b>
            </td>
          </tr>
          <tr :title="`Spec R41a — Present if any hard-to-fix / structural item`">
            <td :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }">
              structuralIntegrityRisk
            </td>
            <td :style="{ padding: '8px 12px' }">
              <b :style="{ color: RISK_COLOR[integrityRisk] }">{{ integrityRisk }}</b>
            </td>
          </tr>
          <template v-if="surfaceMetrics">
            <tr :title="`Spec R24 — sum of CDR loop lengths`">
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                Total CDR length
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.totalCdrLength }}
                <span :style="{ color: '#6b7280' }">{{
                  fmtLowConf(surfaceMetrics.totalCdrLengthLowConfidenceResidueFraction)
                }}</span>
              </td>
            </tr>
            <tr :title="`Spec R25 — Patches of Surface Hydrophobicity`">
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                PSH
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.psh.toFixed(2) }}
                <span :style="{ color: '#6b7280' }"
                  >({{ surfaceMetrics.pshPatchCount }} pairs){{
                    fmtLowConf(surfaceMetrics.pshLowConfidenceResidueFraction)
                  }}</span
                >
              </td>
            </tr>
            <tr :title="`Spec R26 — Patches of Positive Charge`">
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                PPC
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.ppc.toFixed(2) }}
                <span :style="{ color: '#6b7280' }">{{
                  fmtLowConf(surfaceMetrics.ppcLowConfidenceResidueFraction)
                }}</span>
              </td>
            </tr>
            <tr :title="`Spec R26 — Patches of Negative Charge`">
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                PNC
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.pnc.toFixed(2) }}
                <span :style="{ color: '#6b7280' }">{{
                  fmtLowConf(surfaceMetrics.pncLowConfidenceResidueFraction)
                }}</span>
              </td>
            </tr>
            <tr
              v-if="surfaceMetrics.mode === 'TAP' && surfaceMetrics.sfvcsp != null"
              :title="`Spec R28 — Symmetry of Fv Charges Product`"
            >
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                SFvCSP
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.sfvcsp.toFixed(2) }}
                <span :style="{ color: '#6b7280' }">{{
                  fmtLowConf(surfaceMetrics.sfvcspLowConfidenceResidueFraction)
                }}</span>
              </td>
            </tr>
            <tr
              v-if="surfaceMetrics.mode === 'TNP' && surfaceMetrics.cdrh3Compactness != null"
              :title="`Spec R30 — CDRH3 compactness (length / ρ, IMGT anchors)`"
            >
              <td
                :style="{ fontWeight: 'bold', padding: '8px 32px 8px 12px', whiteSpace: 'nowrap' }"
              >
                CDRH3 compactness
              </td>
              <td :style="{ padding: '8px 12px' }">
                {{ surfaceMetrics.cdrh3Compactness.toFixed(3) }}
                <span :style="{ color: '#6b7280' }">{{
                  fmtLowConf(surfaceMetrics.cdrh3CompactnessLowConfidenceResidueFraction)
                }}</span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <PdbLiabilityMap :chains="report.chains" :motifs="report.motifs" />
    </div>

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

    <!-- Spec R51 — per-clonotype scalar metrics table.
         One row per clonotype. Only populated on the PrimaryRef path (the
         workflow emits scoresData as a per-clonotype PFrame keyed on
         scClonotypeKey); on the legacy single-PDB path the table stays in
         its "not ready" state. -->
    <h3 :style="{ margin: '12px 0 6px' }">Per-clonotype developability</h3>
    <p :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }">
      One row per clonotype. Default view shows mode, both risk classes, the composite
      developability score, surfaced motif / exposed extra cys / broken canonical disulfide counts,
      and the Raybould threshold flags (R39, R41a). Raw metric values, motif risk score,
      low-confidence fractions, and totalCdrLength are hidden behind "Columns".
    </p>
    <div :style="{ height: '280px', flexShrink: 0, marginBottom: '16px' }">
      <PlAgDataTableV2
        v-model="scoresLocalState"
        :settings="scoresTableSettings"
        not-ready-text="Run on a predicted-structures dataset to see per-clonotype scores"
        no-rows-text="No scored clonotypes"
      />
    </div>

    <!-- Motifs + cysteines tables. Their PColumn outputs are populated on
         both the legacy single-PDB path and the PrimaryRef per-clonotype
         path (the row axis prepends scClonotypeKey in PrimaryRef mode), so
         they render whenever the workflow has produced data — not gated on
         the single-file `report`. -->
    <!-- Spec R51 drill-downs (motif hits, cysteine state) live on their own
         routes — see the sidebar links. Putting all three tables on one
         page kept AG-Grid stuck in placeholder state (multi-table mount
         race). One PlAgDataTableV2 per page is the working configuration. -->
    <p :style="{ fontSize: '12px', color: '#6b7280', marginTop: '12px' }">
      Per-clonotype detail: see <strong>Motifs</strong> and <strong>Cysteine state</strong>
      pages in the left sidebar for drill-down tables.
    </p>
  </PlBlockPage>
</template>
