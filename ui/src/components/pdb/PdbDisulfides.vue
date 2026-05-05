<script setup lang="ts">
/**
 * PdbDisulfides
 * -------------
 * List of disulfide bonds from SSBOND records — each row shows the two
 * cysteine residues that are covalently linked (chain + residue number for
 * each end). Useful for structural-biology context (Cys-Cys bridges
 * stabilize secondary/tertiary structure) and for confirming whether a
 * model preserves expected disulfides.
 *
 * The whole component is hidden by the parent if `bonds` is empty.
 */
import type { Ssbond } from "../../pdb/parser";

defineProps<{ bonds: Ssbond[] }>();
</script>

<template>
  <h3>Disulfide bonds ({{ bonds.length }})</h3>
  <table>
    <thead>
      <tr>
        <th>Chain A</th>
        <th>Residue A</th>
        <th>Chain B</th>
        <th>Residue B</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(b, i) in bonds" :key="i">
        <td>{{ b.chain1 }}</td>
        <td>{{ b.res1 }}</td>
        <td>{{ b.chain2 }}</td>
        <td>{{ b.res2 }}</td>
      </tr>
    </tbody>
  </table>
</template>
