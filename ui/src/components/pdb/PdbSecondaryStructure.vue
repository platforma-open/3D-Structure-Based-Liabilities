<script setup lang="ts">
/**
 * PdbSecondaryStructure
 * ---------------------
 * Single full-width stacked bar showing what fraction of all residues are
 * helix (H), sheet (E), or coil (C). Driven by HELIX and SHEET records;
 * any residue outside an annotated range is treated as coil.
 *
 * Segments smaller than ~6% of the bar suppress their inline label so the
 * text doesn't overflow into adjacent segments.
 */
import type { SsCounts } from "../../pdb/derivations";
import { fmt } from "../../pdb/styles";

defineProps<{ counts: SsCounts }>();
</script>

<template>
  <details>
    <summary>
      <h3 :style="{ display: 'inline-block', margin: 0 }">Secondary structure</h3>
    </summary>
    <div
      :style="{
        display: 'flex',
        width: '100%',
        height: '28px',
        borderRadius: '3px',
        overflow: 'hidden',
        fontSize: '12px',
      }"
    >
      <div
        :style="{
          width: counts.pctH + '%',
          background: '#ef4444',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          whiteSpace: 'nowrap',
        }"
      >
        <span v-if="counts.pctH > 6">helix {{ fmt(counts.pctH, 1) }}%</span>
      </div>
      <div
        :style="{
          width: counts.pctE + '%',
          background: '#f59e0b',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          whiteSpace: 'nowrap',
        }"
      >
        <span v-if="counts.pctE > 6">sheet {{ fmt(counts.pctE, 1) }}%</span>
      </div>
      <div
        :style="{
          width: counts.pctC + '%',
          background: '#94a3b8',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          whiteSpace: 'nowrap',
        }"
      >
        <span v-if="counts.pctC > 6">coil {{ fmt(counts.pctC, 1) }}%</span>
      </div>
    </div>
  </details>
</template>
