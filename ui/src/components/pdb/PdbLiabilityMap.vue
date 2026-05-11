<script setup lang="ts">
import type {
  ChainSummary,
  MotifHit,
} from "@platforma-open/milabs.3d-structure-based-liabilities.model";
import { computed } from "vue";

const props = defineProps<{
  chains: ChainSummary[];
  motifs: MotifHit[];
}>();

type Category = "deam" | "glyc" | "oxi" | "iso" | "frag" | "hydr" | "integrin";

function motifCategory(type: string): Category {
  if (type.startsWith("Deamidation")) return "deam";
  if (type.startsWith("N-linked Glycosylation")) return "glyc";
  if (type.endsWith("Oxidation (W)") || type.endsWith("Oxidation (M)")) return "oxi";
  if (type.startsWith("Isomerization")) return "iso";
  if (type.startsWith("Fragmentation")) return "frag";
  if (type.startsWith("Hydrolysis")) return "hydr";
  return "integrin";
}

const CATEGORY_COLOR: Record<Category, string> = {
  deam: "#f43f5e",
  glyc: "#8b5cf6",
  oxi: "#14b8a6",
  iso: "#f59e0b",
  frag: "#0ea5e9",
  hydr: "#64748b",
  integrin: "#a855f7",
};

const CATEGORY_LABEL: Record<Category, string> = {
  deam: "Deamidation",
  glyc: "Glycosylation",
  oxi: "Oxidation",
  iso: "Isomerization",
  frag: "Fragmentation",
  hydr: "Hydrolysis",
  integrin: "Integrin",
};

type Marker = { resSeq: number; color: string; tooltip: string };

const rsasaColor = (rsasa: number | null | undefined): string => {
  if (rsasa == null) return "rgba(148, 163, 184, 0.4)";
  const t = Math.max(0, Math.min(1, rsasa));
  const hue = 220 - t * 200;
  const lightness = 35 + t * 30;
  return `hsl(${hue}, 70%, ${lightness}%)`;
};

const chainsView = computed(() => {
  return props.chains.map((chain) => {
    const positions = chain.residues.map((r) => r.resSeq);
    const min = positions.length ? Math.min(...positions) : 0;
    const max = positions.length ? Math.max(...positions) : 1;
    const span = Math.max(1, max - min + 1);

    const markers: Marker[] = [];
    for (const m of props.motifs) {
      if (m.chainId !== chain.id) continue;
      const cat = motifCategory(m.type);
      markers.push({
        resSeq: m.resSeq,
        color: CATEGORY_COLOR[cat],
        tooltip: `${m.resName} ${m.resSeq}${m.iCode} — ${m.type} (rSASA ${m.rsasa.toFixed(2)})`,
      });
    }
    return { id: chain.id, residues: chain.residues, min, max, span, markers };
  });
});

// Only show legend entries for categories that actually have hits.
const legend = computed(() => {
  const present = new Set<Category>(props.motifs.map((m) => motifCategory(m.type)));
  return (Object.keys(CATEGORY_COLOR) as Category[])
    .filter((c) => present.has(c))
    .map((c) => ({ color: CATEGORY_COLOR[c], label: CATEGORY_LABEL[c] }));
});

const rsasaLegend = [0, 0.075, 0.2, 0.4, 0.6, 0.8].map((v) => ({
  color: rsasaColor(v),
  label: v === 0 ? "0" : v === 0.075 ? "0.075 (cutoff)" : v.toFixed(2),
}));
</script>

<template>
  <h3>Residue map</h3>
  <p :style="{ fontSize: '12px', color: '#6b7280' }">
    Per-chain residue axis. Each tick is a residue colored by relative SASA (rSASA): blue = buried,
    orange = exposed. Surface-exposed liability motifs overlay as circles. Hover for details.
  </p>

  <div :style="{ fontSize: '12px', margin: '8px 0' }">
    <div :style="{ marginBottom: '4px', color: '#6b7280' }">rSASA scale</div>
    <div :style="{ display: 'flex', gap: '12px', alignItems: 'center' }">
      <span
        v-for="entry in rsasaLegend"
        :key="entry.label"
        :style="{ display: 'inline-flex', alignItems: 'center' }"
      >
        <span
          :style="{
            display: 'inline-block',
            width: '12px',
            height: '12px',
            background: entry.color,
            marginRight: '6px',
            borderRadius: '2px',
          }"
        />
        {{ entry.label }}
      </span>
    </div>
  </div>

  <div
    v-if="legend.length"
    :style="{
      display: 'flex',
      flexWrap: 'wrap',
      gap: '16px',
      fontSize: '12px',
      margin: '8px 0 12px',
    }"
  >
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

  <div v-for="chain in chainsView" :key="chain.id" :style="{ marginBottom: '12px' }">
    <div :style="{ fontSize: '12px', color: '#6b7280', marginBottom: '2px' }">
      Chain {{ chain.id }} ({{ chain.residues.length }} residues, {{ chain.min }}–{{ chain.max }})
    </div>
    <svg
      :viewBox="`${chain.min - 1} 0 ${chain.span + 1} 20`"
      preserveAspectRatio="none"
      :style="{
        width: '100%',
        height: '24px',
        display: 'block',
        background: 'rgba(148, 163, 184, 0.08)',
      }"
    >
      <rect
        v-for="(r, i) in chain.residues"
        :key="i"
        :x="r.resSeq"
        :y="6"
        :width="0.95"
        :height="8"
        :fill="rsasaColor(r.rsasa)"
      >
        <title>
          {{ r.resName }} {{ r.resSeq }}{{ r.iCode }} — rSASA
          {{ r.rsasa == null ? "n/a" : r.rsasa.toFixed(3) }}
        </title>
      </rect>
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
