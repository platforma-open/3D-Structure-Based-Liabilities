<script setup lang="ts">
import type {
  LiabilitiesReport,
  MotifHit,
} from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { computed } from "vue";

/**
 * Spec R53 , per-clonotype detail panel. Renders an expanded liability
 * list grouped by motif type, the cysteine state summary, surface metrics
 * with flag colors, and the composite developability score, all read from
 * the per-clonotype `liabilities.json` report. Lives next to the Mol*
 * viewer in the R52 modal so the user sees structural context and the
 * categorical readout side-by-side. Per-residue highlighting into the
 * viewer is deferred (requires viewer annotation API).
 */
const props = defineProps<{
  report: LiabilitiesReport | null;
  clonotypeKey: string;
  clonotypeLabel?: string;
}>();

const FLAG_COLOR: Record<string, string> = {
  green: "#65a30d",
  amber: "#d97706",
  red: "#dc2626",
};

const motifsByType = computed<Record<string, MotifHit[]>>(() => {
  const out: Record<string, MotifHit[]> = {};
  for (const m of props.report?.motifs ?? []) {
    (out[m.type] ??= []).push(m);
  }
  return out;
});

// Spec R35 , gated motifs render in their own section so the user can
// see what was confidence-suppressed without it polluting the confident-
// call list above.
const uncertainByType = computed<Record<string, MotifHit[]>>(() => {
  const out: Record<string, MotifHit[]> = {};
  for (const m of props.report?.uncertainLiabilities ?? []) {
    (out[m.type] ??= []).push(m);
  }
  return out;
});

const cysteines = computed(() => props.report?.cysteines ?? []);

const flags = computed<Record<string, string>>(() => {
  const sm = props.report as unknown as { thresholdFlags?: Record<string, string> };
  return sm?.thresholdFlags ?? {};
});

function pctRsasa(v: number | undefined | null): string {
  return v == null ? "-" : `${Math.round(v * 100)}%`;
}

function fmtConf(v: number | null): string {
  return v == null ? "-" : `${v.toFixed(2)} Å`;
}
</script>

<template>
  <div :class="$style.panel">
    <header :class="$style.header">
      <div :class="$style.title">{{ clonotypeLabel || clonotypeKey }}</div>
      <div v-if="clonotypeLabel && clonotypeLabel !== clonotypeKey" :class="$style.subtitle">
        {{ clonotypeKey }}
      </div>
    </header>

    <section
      v-if="report?.surfaceMetrics && 'mode' in report.surfaceMetrics"
      :class="$style.section"
    >
      <h3 :class="$style.h3">Surface metrics</h3>
      <table :class="$style.kv">
        <tbody>
          <tr
            v-for="m in [
              {
                id: 'totalCdrLength',
                label: 'Total CDR length',
                v: report.surfaceMetrics.totalCdrLength,
                flag: flags.totalCdrLengthFlag,
              },
              {
                id: 'psh',
                label: 'PSH',
                v: report.surfaceMetrics.psh?.toFixed?.(2),
                flag: flags.pshFlag,
              },
              {
                id: 'ppc',
                label: 'PPC',
                v: report.surfaceMetrics.ppc?.toFixed?.(2),
                flag: flags.ppcFlag,
              },
              {
                id: 'pnc',
                label: 'PNC',
                v: report.surfaceMetrics.pnc?.toFixed?.(2),
                flag: flags.pncFlag,
              },
              {
                id: 'sfvcsp',
                label: 'SFvCSP',
                v: report.surfaceMetrics.sfvcsp?.toFixed?.(2),
                flag: flags.sfvcspFlag,
              },
              {
                id: 'cdrh3Compactness',
                label: 'CDRH3 compactness',
                v: report.surfaceMetrics.cdrh3Compactness?.toFixed?.(3),
                flag: flags.cdrh3CompactnessFlag,
              },
            ]"
            :key="m.id"
            v-show="m.v !== undefined && m.v !== null"
          >
            <td :class="$style.kvKey">{{ m.label }}</td>
            <td
              :class="$style.kvValue"
              :style="
                m.flag && m.flag !== '-' ? { color: FLAG_COLOR[m.flag], fontWeight: 600 } : {}
              "
            >
              {{ m.v ?? "-" }}
            </td>
            <td>
              <span
                v-if="m.flag === 'red'"
                :class="$style.flagBadge"
                :style="{ background: FLAG_COLOR.red + '33', color: FLAG_COLOR.red }"
              >
                {{ m.flag }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="Object.keys(motifsByType).length > 0" :class="$style.section">
      <h3 :class="$style.h3">Motifs ({{ report?.scores?.surfacedMotifCount ?? 0 }})</h3>
      <div v-for="(hits, type) in motifsByType" :key="type" :class="$style.motifGroup">
        <div :class="$style.motifGroupHead">
          {{ type }} <span :class="$style.muted">× {{ hits.length }}</span>
        </div>
        <table :class="$style.motifTable">
          <tbody>
            <tr v-for="h in hits" :key="`${h.chainId}-${h.resSeq}-${h.iCode}-${h.type}`">
              <td :class="$style.motifSite">{{ h.chainId }}/{{ h.resSeq }}{{ h.iCode }}</td>
              <td :class="$style.motifRegion">{{ h.region ?? "-" }}</td>
              <td :class="$style.motifRsasa">rSASA {{ pctRsasa(h.rsasa) }}</td>
              <td :class="$style.motifConf">B {{ fmtConf(h.confidence) }}</td>
              <td :class="$style.motifScore">
                <span v-if="h.confidenceGated === 'yes'" :class="$style.gated">gated</span>
                <span v-else>{{ h.weightedScore.toFixed(2) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="Object.keys(uncertainByType).length > 0" :class="$style.section">
      <h3 :class="$style.h3">
        Uncertain liabilities
        <span :class="$style.muted">
          × {{ report?.uncertainLiabilities?.length ?? 0 }} (R35 , gated by B-factor)
        </span>
      </h3>
      <div v-for="(hits, type) in uncertainByType" :key="type" :class="$style.motifGroup">
        <div :class="$style.motifGroupHead">
          {{ type }} <span :class="$style.muted">× {{ hits.length }}</span>
        </div>
        <table :class="$style.motifTable">
          <tbody>
            <tr v-for="h in hits" :key="`${h.chainId}-${h.resSeq}-${h.iCode}-${h.type}`">
              <td :class="$style.motifSite">{{ h.chainId }}/{{ h.resSeq }}{{ h.iCode }}</td>
              <td :class="$style.motifRegion">{{ h.region ?? "-" }}</td>
              <td :class="$style.motifRsasa">rSASA {{ pctRsasa(h.rsasa) }}</td>
              <td :class="$style.motifConf">B {{ fmtConf(h.confidence) }}</td>
              <td :class="$style.motifScore">
                <span :class="$style.gated">gated</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="cysteines.length > 0" :class="$style.section">
      <h3 :class="$style.h3">Cysteines ({{ cysteines.length }})</h3>
      <table :class="$style.motifTable">
        <tbody>
          <tr v-for="c in cysteines" :key="`${c.chainId}-${c.resSeq}-${c.iCode}`">
            <td :class="$style.motifSite">{{ c.chainId }}/{{ c.resSeq }}{{ c.iCode }}</td>
            <td>{{ c.cysClass }}</td>
            <td>{{ c.bondingState }}</td>
            <td :class="$style.motifRsasa">side {{ pctRsasa(c.sidechainRsasa) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <p v-if="!report" :class="$style.empty">Loading liabilities report…</p>
  </div>
</template>

<style module>
.panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 12px 16px;
  font-size: 13px;
  color: #1f2937;
  background: #fff;
  border-left: 1px solid #e5e7eb;
}

.header {
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 8px;
}

.title {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.subtitle {
  font-size: 11px;
  color: #6b7280;
  font-family: monospace;
  margin-top: 2px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.h3 {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
  margin: 0;
}

.kv {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.kvKey {
  color: #6b7280;
  padding: 3px 8px 3px 0;
}

.kvValue {
  font-weight: 500;
  padding: 3px 8px 3px 0;
  text-align: right;
}

.flagBadge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.motifGroup {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.motifGroupHead {
  font-size: 12px;
  font-weight: 600;
  color: #374151;
  background: rgba(148, 163, 184, 0.1);
  padding: 4px 8px;
  border-radius: 3px;
}

.muted {
  color: #6b7280;
  font-weight: 400;
}

.motifTable {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.motifTable td {
  padding: 3px 6px;
  border-bottom: 1px solid #f3f4f6;
}

.motifSite {
  font-family: monospace;
  font-size: 11px;
  white-space: nowrap;
}

.motifRegion {
  color: #6b7280;
  font-size: 11px;
}

.motifRsasa,
.motifConf {
  color: #6b7280;
  font-size: 11px;
  white-space: nowrap;
}

.motifScore {
  text-align: right;
  font-weight: 500;
}

.gated {
  font-size: 10px;
  color: #d97706;
  font-style: italic;
}

.empty {
  color: #6b7280;
  font-style: italic;
}
</style>
