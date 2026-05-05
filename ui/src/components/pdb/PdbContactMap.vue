<script setup lang="ts">
/**
 * PdbContactMap
 * -------------
 * 2D heatmap of CA-CA distances for the largest chain. Cells where the
 * distance is ≤ 8 Å are shaded teal; closer pairs render darker (intensity
 * = 1 - d/8). The diagonal is 0 Å (residue with itself) and shows up as
 * the strongest line.
 *
 * Reveals tertiary structure at a glance:
 *  - Diagonal-adjacent shading = local sequence contacts (helices/sheets).
 *  - Off-diagonal blocks = long-range contacts (β-sheet pairings, domain
 *    interfaces, disulfide bridges).
 *
 * For chains larger than 200 residues, the matrix is downsampled stride-N
 * (every Nth residue) so rendering stays interactive on large structures.
 * The downsampling factor is exposed in the heading.
 *
 * Drawn into a `<canvas>` rather than an SVG/grid because n×n DOM nodes
 * (up to 40,000) would be slow to mount and lay out.
 */
import { ref, watchEffect } from "vue";
import type { ContactMap } from "../../pdb/derivations";

const props = defineProps<{ data: ContactMap }>();

const canvas = ref<HTMLCanvasElement>();

watchEffect(() => {
  const cv = canvas.value;
  if (!cv) return;
  const cm = props.data;
  const cell = Math.max(2, Math.floor(480 / cm.n));
  cv.width = cm.n * cell;
  cv.height = cm.n * cell;
  const ctx = cv.getContext("2d")!;
  ctx.clearRect(0, 0, cv.width, cv.height);
  for (let i = 0; i < cm.n; i++)
    for (let j = 0; j < cm.n; j++) {
      const d = cm.matrix[i * cm.n + j];
      if (d <= 8) {
        const intensity = Math.max(0.15, 1 - d / 8);
        ctx.fillStyle = `rgba(20, 184, 166, ${intensity})`;
        ctx.fillRect(j * cell, i * cell, cell, cell);
      }
    }
});
</script>

<template>
  <h3>
    Contact map — chain {{ data.chainId }} ({{ data.n }} residues<span v-if="data.stride > 1"
      >, every {{ data.stride }}th</span
    >)
  </h3>
  <canvas ref="canvas" />
</template>
