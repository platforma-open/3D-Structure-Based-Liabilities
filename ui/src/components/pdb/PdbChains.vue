<script setup lang="ts">
/**
 * PdbChains
 * ---------
 * Per-chain summary table with three visual encodings:
 *  - **Residues bar** (blue): residue count, scaled to the largest chain.
 *  - **Atoms bar** (teal): atom count, scaled to the largest chain.
 *  - **B-factor sparkline** (amber SVG): per-residue mean B-factor along the
 *    chain, drawn as one rect per residue. Shows where the structure is
 *    flexible / disordered.
 *
 * All four columns share the same chain ordering as the parser produced
 * (i.e., first ATOM occurrence per chain).
 */
import { computed } from "vue";
import type { BFactorProfile, ChainStat } from "../../pdb/derivations";
import { bar, barCellStyle, barTextStyle, pct } from "../../pdb/styles";

const props = defineProps<{
  chains: ChainStat[];
  bFactorProfiles: Map<string, BFactorProfile>;
}>();

const maxResidues = computed(() => Math.max(1, ...props.chains.map((c) => c.residues)));
const maxAtoms = computed(() => Math.max(1, ...props.chains.map((c) => c.atoms)));
</script>

<template>
  <details>
    <summary>
      <h3 :style="{ display: 'inline-block', margin: 0 }">Chains</h3>
    </summary>
    <table>
      <thead>
        <tr>
          <th>Chain</th>
          <th>Residues</th>
          <th>Atoms</th>
          <th>B-factor profile</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in chains" :key="c.id">
          <td>{{ c.id }}</td>
          <td :style="barCellStyle">
            <div :style="bar(pct(c.residues, maxResidues), 'rgba(59, 130, 246, 0.35)')" />
            <span :style="barTextStyle">{{ c.residues }}</span>
          </td>
          <td :style="barCellStyle">
            <div :style="bar(pct(c.atoms, maxAtoms), 'rgba(20, 184, 166, 0.35)')" />
            <span :style="barTextStyle">{{ c.atoms }}</span>
          </td>
          <td>
            <svg
              v-if="bFactorProfiles.get(c.id)"
              :viewBox="`0 0 ${bFactorProfiles.get(c.id)!.values.length} 24`"
              preserveAspectRatio="none"
              :style="{ width: '100%', height: '24px', display: 'block' }"
            >
              <rect
                v-for="(v, i) in bFactorProfiles.get(c.id)!.values"
                :key="i"
                :x="i"
                :y="24 - (v / bFactorProfiles.get(c.id)!.max) * 24"
                :width="1"
                :height="(v / bFactorProfiles.get(c.id)!.max) * 24"
                fill="rgba(245, 158, 11, 0.7)"
              />
            </svg>
          </td>
        </tr>
      </tbody>
    </table>
  </details>
</template>
