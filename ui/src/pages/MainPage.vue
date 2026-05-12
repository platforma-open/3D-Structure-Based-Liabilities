<script setup lang="ts">
import type { LiabilitiesReport } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import {
  computedResult,
  PlAccordionSection,
  PlAgDataTableV2,
  PlBlockPage,
  PlDropdown,
  PlFileInput,
  PlNumberField,
  usePlDataTableSettingsV2,
} from "@platforma-sdk/ui-vue";
import { computed } from "vue";
import { useApp } from "../app";

import PdbLiabilityMap from "../components/pdb/PdbLiabilityMap.vue";

// Spec R12 — Raybould 2019 canonical cutoff. rSASA below this is "buried".
const BURIED_CUTOFF = 0.075;

const app = useApp();
const liabilitiesJson = computedResult(() => app.model.outputs.liabilitiesJson);

const report = computed<LiabilitiesReport | null>(() => {
  const text = liabilitiesJson.value.value;
  return text ? (JSON.parse(text) as LiabilitiesReport) : null;
});

// sourceId discriminator scopes the AG-Grid stateCache to each table's shape.
// Bump the version suffix whenever the PColumn axes/columns shape changes so
// AG-Grid can't reuse a column-order/hidden-cols cache built against the old
// shape (we lost ~a day to a residueData→motifsData migration where the
// persisted cache pointed at columns that no longer existed).
const motifsTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.motifsTable,
  // bumped v1 → v2 when confidence + confidenceGated columns were added (R34-R36).
  sourceId: () => "motifs-v2",
});
const cysTableSettings = usePlDataTableSettingsV2({
  model: () => app.model.outputs.cysTable,
  // bumped v1 → v2 when cysClass + chainRole columns were added (R21-R23).
  sourceId: () => "cysteines-v2",
});

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
  <PlBlockPage>
    <PlFileInput
      v-model="app.model.data.pdb"
      label="PDB file"
      :extensions="['.pdb']"
      placeholder="Drop a .pdb file"
      required
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

      <h3 :style="{ margin: '12px 0 6px' }">Surface-exposed liability motifs</h3>
      <p :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }">
        One row per surfaced motif hit. Rows are filterable / sortable; axis order is Chain,
        Position, Insertion code, Motif. Buried matches (rSASA &lt;
        {{ BURIED_CUTOFF }}) are dropped upstream and never appear here.
      </p>
      <div :style="{ height: '360px', marginBottom: '16px' }">
        <PlAgDataTableV2
          v-model="app.model.data.tableState"
          :settings="motifsTableSettings"
          not-ready-text="Run on a PDB to see surfaced motifs"
          no-rows-text="No surface-exposed motifs detected"
        />
      </div>

      <h3 :style="{ margin: '12px 0 6px' }">Cysteine state</h3>
      <p :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '8px' }">
        Every Cys residue with its disulfide-bond partner (SG–SG ≤ 3.0 Å and Cα–Cα ≤ 7.0 Å). When a
        numbering scheme + chain role are set, each Cys is classified per spec R21–R23:
        <code>disulfide</code>, <code>disulfide_broken</code>,
        <code>disulfide_missing</code> (phantom row at the expected position), or
        <code>cys_extra</code>.
      </p>
      <div :style="{ height: '280px', marginBottom: '16px' }">
        <PlAgDataTableV2
          v-model="app.model.data.cysTableState"
          :settings="cysTableSettings"
          not-ready-text="Run on a PDB to see cysteine state"
          no-rows-text="No cysteines found"
        />
      </div>

      <PdbLiabilityMap :chains="report.chains" :motifs="report.motifs" />
    </div>
  </PlBlockPage>
</template>
