<script setup lang="ts">
/**
 * PdbSequences
 * ------------
 * Per-chain primary sequence rendered as a strip of small colored boxes,
 * one per residue. Encodes two dimensions per residue:
 *  - **Background color**: chemistry class — hydrophobic (amber), polar
 *    (teal), acidic (rose), basic (blue), other / non-standard (grey).
 *  - **Bottom-border color**: secondary structure — helix (red),
 *    sheet (orange), coil (none).
 *
 * Hovering a box shows the original 3-letter code, the residue number, and
 * the SS state. Non-standard residues collapse to "·".
 */
import type { SequenceChain } from "../../pdb/derivations";
import { AA_COLOR, SS_COLOR } from "../../pdb/constants";

defineProps<{ sequences: SequenceChain[] }>();
</script>

<template>
  <h3>Sequences</h3>
  <div v-for="s in sequences" :key="s.id">
    <div :style="{ fontSize: '12px', color: '#6b7280' }">
      Chain {{ s.id }} ({{ s.letters.length }} aa)
    </div>
    <div
      :style="{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '1px',
        fontFamily: 'ui-monospace, SFMono-Regular, monospace',
        fontSize: '11px',
      }"
    >
      <span
        v-for="(r, i) in s.letters"
        :key="i"
        :style="{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '14px',
          height: '16px',
          background: AA_COLOR[r.cls],
          borderBottom: `2px solid ${SS_COLOR[r.ss]}`,
        }"
        :title="`${r.resName} ${r.resSeq} (${r.ss})`"
        >{{ r.letter }}</span
      >
    </div>
  </div>
</template>
