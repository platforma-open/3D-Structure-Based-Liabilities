<script setup lang="ts">
/**
 * PdbModifiedResidues
 * -------------------
 * List of post-translationally modified or non-standard residues from
 * MODRES records. Each row maps the modified residue code back to the
 * standard residue it replaces, with the chain/sequence position and the
 * free-text comment from the PDB describing the modification (e.g.
 * "PHOSPHORYLATION", "SELENOMETHIONINE").
 *
 * Hidden by the parent if `modres` is empty.
 */
import type { Modres } from "../../pdb/parser";

defineProps<{ modres: Modres[] }>();
</script>

<template>
  <h3>Modified residues ({{ modres.length }})</h3>
  <table>
    <thead>
      <tr>
        <th>Residue</th>
        <th>Std</th>
        <th>Chain</th>
        <th>Seq</th>
        <th>Comment</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(m, i) in modres" :key="i">
        <td>{{ m.resName }}</td>
        <td>{{ m.stdName }}</td>
        <td>{{ m.chainId }}</td>
        <td>{{ m.resSeq }}</td>
        <td>{{ m.comment }}</td>
      </tr>
    </tbody>
  </table>
</template>
