<script setup lang="ts">
/**
 * PdbValidation
 * -------------
 * Per-chain structural-quality flags, useful for triaging messy structures
 * before downstream analysis:
 *  - **Missing backbone**: count of residues lacking at least one of
 *    N / CA / C / O. Indicates incomplete model building.
 *  - **Sequence gaps**: count of residue-number jumps > 1 between adjacent
 *    residues in the chain. Indicates unresolved loops.
 *  - **Alt-locs**: number of distinct alt-loc identifiers present in this
 *    chain (e.g., A/B/C). Indicates conformational disorder.
 */
import type { ValidationRow } from "../../pdb/derivations";

defineProps<{ rows: ValidationRow[] }>();
</script>

<template>
  <h3>Validation</h3>
  <table>
    <thead>
      <tr>
        <th>Chain</th>
        <th>Missing backbone</th>
        <th>Sequence gaps</th>
        <th>Alt-locs</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="v in rows" :key="v.id">
        <td>{{ v.id }}</td>
        <td>{{ v.missing }}</td>
        <td>{{ v.gaps }}</td>
        <td>{{ v.altLocs }}</td>
      </tr>
    </tbody>
  </table>
</template>
