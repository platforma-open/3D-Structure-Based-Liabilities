<script setup lang="ts">
/**
 * PdbLiabilityList
 * ----------------
 * Generic table renderer for any of the sequence-based liability detectors.
 * Each row is a single hit and shows: chain, residue (3-letter), position,
 * and — when present in the data — a `motif` and/or `context` column.
 *
 * The component itself is intentionally domain-agnostic: it does not know
 * what kind of liability it is rendering. The science (which residues
 * count, what the motif means) lives in `src/pdb/liabilities.ts`. The
 * `description` prop carries a short human-readable explanation that the
 * parent passes through, so users can read what the section means without
 * jumping to the source.
 *
 * The whole component (heading + description + table) is hidden by the
 * parent if `hits` is empty — empty liabilities are a feature, not a row.
 */
import { computed } from "vue";
import type { LiabilityHit } from "../../pdb/liabilities";

const props = defineProps<{
  title: string;
  description?: string;
  hits: LiabilityHit[];
}>();

const hasMotif = computed(() => props.hits.some((h) => h.motif));
const hasContext = computed(() => props.hits.some((h) => h.context));
</script>

<template>
  <h3>{{ title }} ({{ hits.length }})</h3>
  <p v-if="description" :style="{ fontSize: '12px', color: '#6b7280', marginTop: '-0.5rem' }">
    {{ description }}
  </p>
  <table>
    <thead>
      <tr>
        <th>Chain</th>
        <th>Residue</th>
        <th>Position</th>
        <th v-if="hasMotif">Motif</th>
        <th v-if="hasContext">Context</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(h, i) in hits" :key="i">
        <td>{{ h.chainId }}</td>
        <td>{{ h.resName }}</td>
        <td>{{ h.resSeq }}</td>
        <td v-if="hasMotif">{{ h.motif ?? "—" }}</td>
        <td v-if="hasContext">{{ h.context ?? "—" }}</td>
      </tr>
    </tbody>
  </table>
</template>
