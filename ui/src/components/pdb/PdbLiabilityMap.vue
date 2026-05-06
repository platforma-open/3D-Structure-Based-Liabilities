<script setup lang="ts">
/**
 * PdbLiabilityMap
 * ---------------
 * Per-chain sequence strip with liability hits marked at their resSeq
 * positions. Each chain renders as a horizontal SVG; small grey ticks mark
 * residue positions along the X axis, colored circles mark liabilities.
 * Color encodes liability type, position along X encodes residue position.
 *
 * Answers "where in the chain do liabilities cluster?" at a glance —
 * complements the four detail tables which list one row per hit.
 */
import { computed } from "vue";
import type { LiabilityHit } from "../../pdb/liabilities";
import type { Parsed } from "../../pdb/parser";

const props = defineProps<{
  parsed: Parsed;
  unpairedCys: LiabilityHit[];
  deamidations: LiabilityHit[];
  glycosylations: LiabilityHit[];
  oxidations: LiabilityHit[];
}>();

const TYPE_COLOR = {
  cys: "#f59e0b",
  deam: "#f43f5e",
  glyc: "#8b5cf6",
  oxi: "#14b8a6",
} as const;

type Marker = { resSeq: number; color: string; tooltip: string };

const chains = computed(() => {
  return props.parsed.chainOrder.map((id) => {
    const residues = props.parsed.residuesByChain.get(id)!;
    const positions = residues.map((r) => r.resSeq);
    const min = positions.length ? Math.min(...positions) : 0;
    const max = positions.length ? Math.max(...positions) : 1;
    const span = Math.max(1, max - min + 1);

    const markers: Marker[] = [];
    const push = (hit: LiabilityHit, color: string, label: string, extra = ""): void => {
      if (hit.chainId !== id) return;
      const pos = `${hit.resSeq}${hit.iCode}`;
      markers.push({
        resSeq: hit.resSeq,
        color,
        tooltip: `${hit.resName} ${pos} — ${label}${extra}`,
      });
    };
    for (const h of props.unpairedCys) push(h, TYPE_COLOR.cys, "unpaired Cys");
    for (const h of props.deamidations)
      push(h, TYPE_COLOR.deam, "deamidation", h.motif ? ` (${h.motif})` : "");
    for (const h of props.glycosylations)
      push(h, TYPE_COLOR.glyc, "glycosylation sequon", h.motif ? ` (${h.motif})` : "");
    for (const h of props.oxidations) push(h, TYPE_COLOR.oxi, "oxidation-prone");

    return { id, residues, min, max, span, markers };
  });
});

const legend = [
  { color: TYPE_COLOR.cys, label: "Unpaired Cys" },
  { color: TYPE_COLOR.deam, label: "Deamidation" },
  { color: TYPE_COLOR.glyc, label: "Glycosylation sequon" },
  { color: TYPE_COLOR.oxi, label: "Oxidation-prone" },
];
</script>

<template>
  <h3>Liability map</h3>
  <p :style="{ fontSize: '12px', color: '#6b7280' }">
    Per-chain residue axis with liability positions marked. Color encodes type; hover for details.
  </p>
  <div :style="{ display: 'flex', gap: '16px', fontSize: '12px', margin: '8px 0' }">
    <span
      v-for="l in legend"
      :key="l.label"
      :style="{ display: 'inline-flex', alignItems: 'center' }"
    >
      <span
        :style="{
          display: 'inline-block',
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          background: l.color,
          marginRight: '6px',
        }"
      />
      {{ l.label }}
    </span>
  </div>
  <div v-for="chain in chains" :key="chain.id" :style="{ marginBottom: '8px' }">
    <div :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }">
      Chain {{ chain.id }} ({{ chain.residues.length }} residues, {{ chain.min }}–{{ chain.max }})
    </div>
    <svg
      :viewBox="`${chain.min - 1} 0 ${chain.span + 1} 20`"
      preserveAspectRatio="none"
      :style="{
        width: '100%',
        height: '20px',
        display: 'block',
        background: 'rgba(148, 163, 184, 0.08)',
      }"
    >
      <rect
        v-for="(r, i) in chain.residues"
        :key="i"
        :x="r.resSeq"
        :y="9"
        :width="0.6"
        :height="2"
        fill="rgba(100, 116, 139, 0.4)"
      />
      <circle
        v-for="(m, i) in chain.markers"
        :key="i"
        :cx="m.resSeq + 0.5"
        :cy="10"
        :r="1.6"
        :fill="m.color"
      >
        <title>{{ m.tooltip }}</title>
      </circle>
    </svg>
  </div>
</template>
