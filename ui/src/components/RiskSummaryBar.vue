<script setup lang="ts">
import type { LiabilitiesReport } from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { computed } from "vue";

/**
 * Spec R41 / R41a — risk readout shown above the 3D viewer. Pulled out
 * of ClonotypeDetailPanel so it sits in the tab page header where the
 * user reads it first, before the structure. Same fields the detail
 * panel used: mode, composite developability score, fixable-risk
 * categorical, integrity-risk categorical.
 */
const props = defineProps<{
  report: LiabilitiesReport | null;
}>();

const RISK_COLOR: Record<string, string> = {
  None: "#65a30d",
  Low: "#84cc16",
  Medium: "#d97706",
  High: "#dc2626",
  Present: "#dc2626",
};

const scores = computed(() => props.report?.scores);
</script>

<template>
  <div :class="$style.bar">
    <div :class="$style.cell">
      <span :class="$style.label">Mode</span>
      <span :class="$style.value">{{ report?.mode ?? "—" }}</span>
    </div>
    <div :class="$style.cell">
      <span :class="$style.label">Dev. score</span>
      <span :class="$style.value">
        {{ scores ? scores.structuralDevelopabilityScore.toFixed(2) : "—" }}
      </span>
    </div>
    <div :class="$style.cell">
      <span :class="$style.label">Dev. risk</span>
      <span
        v-if="scores"
        :class="$style.badge"
        :style="{
          background: RISK_COLOR[scores.structuralDevelopabilityRisk] + '22',
          color: RISK_COLOR[scores.structuralDevelopabilityRisk],
        }"
      >
        {{ scores.structuralDevelopabilityRisk }}
      </span>
      <span v-else :class="$style.value">—</span>
    </div>
    <div :class="$style.cell">
      <span :class="$style.label">Integrity</span>
      <span
        v-if="scores"
        :class="$style.badge"
        :style="{
          background: RISK_COLOR[scores.structuralIntegrityRisk] + '22',
          color: RISK_COLOR[scores.structuralIntegrityRisk],
        }"
      >
        {{ scores.structuralIntegrityRisk }}
      </span>
      <span v-else :class="$style.value">—</span>
    </div>
  </div>
</template>

<style module>
.bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 8px;
  padding: 10px 12px;
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  margin-bottom: 12px;
}

.cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: #1f2937;
  padding: 4px 6px;
}

.label {
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.value {
  font-weight: 600;
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: 10px;
}
</style>
