<script setup lang="ts">
/**
 * PdbSummary
 * ----------
 * Top-level metadata table. Renders the high-level scalar fields extracted
 * from PDB header records: HEADER, TITLE, EXPDTA (experimental method),
 * REMARK 2 (resolution), REMARK 3 (R-factor / R-free), MODEL count,
 * ATOM/HETATM counts, chain count, total residues, bounding box (XYZ
 * extents), centroid (mean XYZ), CRYST1 unit cell, and the set of alt-loc
 * identifiers if any.
 *
 * Each row is conditional — rows are only rendered if the underlying field
 * is actually populated, so the table stays compact for sparse PDB files.
 */
import type { Parsed } from "../../pdb/parser";
import type { Bounds, ChainStat } from "../../pdb/derivations";
import { fmt } from "../../pdb/styles";

defineProps<{
  parsed: Parsed;
  chains: ChainStat[];
  bounds: Bounds | null;
}>();
</script>

<template>
  <h3>Summary</h3>
  <table>
    <tbody>
      <tr v-if="parsed.header">
        <th>Header</th>
        <td>{{ parsed.header }}</td>
      </tr>
      <tr v-if="parsed.title">
        <th>Title</th>
        <td>{{ parsed.title }}</td>
      </tr>
      <tr v-if="parsed.experimentalMethod">
        <th>Method</th>
        <td>{{ parsed.experimentalMethod }}</td>
      </tr>
      <tr v-if="parsed.resolution !== null">
        <th>Resolution</th>
        <td>{{ fmt(parsed.resolution) }} Å</td>
      </tr>
      <tr v-if="parsed.rFactor !== null">
        <th>R-factor</th>
        <td>
          {{ fmt(parsed.rFactor, 3)
          }}<span v-if="parsed.rFree !== null"> / R-free {{ fmt(parsed.rFree, 3) }}</span>
        </td>
      </tr>
      <tr>
        <th>Models</th>
        <td>{{ parsed.models || 1 }}</td>
      </tr>
      <tr>
        <th>ATOM records</th>
        <td>{{ parsed.atomCount }}</td>
      </tr>
      <tr>
        <th>HETATM records</th>
        <td>{{ parsed.hetatmCount }}</td>
      </tr>
      <tr>
        <th>Chains</th>
        <td>{{ chains.length }}</td>
      </tr>
      <tr>
        <th>Total residues</th>
        <td>{{ chains.reduce((n, c) => n + c.residues, 0) }}</td>
      </tr>
      <tr v-if="bounds">
        <th>Bounding box</th>
        <td>{{ fmt(bounds.dx, 1) }} × {{ fmt(bounds.dy, 1) }} × {{ fmt(bounds.dz, 1) }} Å</td>
      </tr>
      <tr v-if="bounds">
        <th>Centroid</th>
        <td>({{ fmt(bounds.cx, 1) }}, {{ fmt(bounds.cy, 1) }}, {{ fmt(bounds.cz, 1) }})</td>
      </tr>
      <tr v-if="parsed.cryst">
        <th>Unit cell</th>
        <td>
          {{ fmt(parsed.cryst.a, 2) }} × {{ fmt(parsed.cryst.b, 2) }} ×
          {{ fmt(parsed.cryst.c, 2) }} Å, α={{ fmt(parsed.cryst.alpha, 1) }}° β={{
            fmt(parsed.cryst.beta, 1)
          }}° γ={{ fmt(parsed.cryst.gamma, 1) }}°
          <span v-if="parsed.cryst.spaceGroup">({{ parsed.cryst.spaceGroup }})</span>
        </td>
      </tr>
      <tr v-if="parsed.altLocs.size">
        <th>Alt-locs</th>
        <td>{{ [...parsed.altLocs].sort().join(", ") }}</td>
      </tr>
    </tbody>
  </table>
</template>
