<script setup lang="ts">
import { computed } from "vue";

/**
 * Spec R54 — histogram of a single metric across all clonotypes, with
 * Raybould 2019 / Gordon 2025 amber/red threshold values overlaid as
 * dashed vertical lines (so the user can read where each band sits
 * without leaving the chart).
 *
 * Pure SVG so the threshold annotation is honored — graph-maker's
 * histogram template currently ignores `pl7.app/graph/thresholds`, which
 * was the gap the strip plot solved at small N. This component closes the
 * same gap at large N.
 */
type Threshold = { value: number; color?: string };

const props = defineProps<{
  values: number[];
  thresholds?: Threshold[];
  binsCount?: number;
  axisLabel?: string;
}>();

const PADDING = { top: 24, right: 24, bottom: 36, left: 36 };
const WIDTH = 760;
const HEIGHT = 320;
const PLOT_W = WIDTH - PADDING.left - PADDING.right;
const PLOT_H = HEIGHT - PADDING.top - PADDING.bottom;

const DEFAULT_BINS = 24;

const xDomain = computed(() => {
  const all: number[] = [...props.values];
  if (props.thresholds) {
    for (const t of props.thresholds) all.push(t.value);
  }
  if (all.length === 0) return { min: 0, max: 1 };
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) {
    const pad = Math.abs(min) > 0 ? Math.abs(min) * 0.1 : 1;
    min -= pad;
    max += pad;
  } else {
    const pad = (max - min) * 0.05;
    min -= pad;
    max += pad;
  }
  return { min, max };
});

type Bin = { x0: number; x1: number; count: number };

const bins = computed<Bin[]>(() => {
  const n = props.binsCount ?? DEFAULT_BINS;
  const { min, max } = xDomain.value;
  const step = (max - min) / n;
  const out: Bin[] = [];
  for (let i = 0; i < n; i++) {
    out.push({ x0: min + i * step, x1: min + (i + 1) * step, count: 0 });
  }
  for (const v of props.values) {
    if (Number.isNaN(v)) continue;
    let idx = Math.floor(((v - min) / (max - min)) * n);
    if (idx >= n) idx = n - 1;
    if (idx < 0) idx = 0;
    out[idx].count++;
  }
  return out;
});

const maxCount = computed(() => Math.max(1, ...bins.value.map((b) => b.count)));

function xFor(value: number): number {
  const { min, max } = xDomain.value;
  return PADDING.left + ((value - min) / (max - min)) * PLOT_W;
}

function yForCount(count: number): number {
  return PADDING.top + PLOT_H - (count / maxCount.value) * PLOT_H;
}

const xTicks = computed<number[]>(() => {
  const { min, max } = xDomain.value;
  const targetCount = 5;
  const rawStep = (max - min) / targetCount;
  const pow = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / pow;
  const niceStep = (norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * pow;
  const startVal = Math.ceil(min / niceStep) * niceStep;
  const out: number[] = [];
  for (let v = startVal; v <= max + niceStep * 0.001; v += niceStep) {
    out.push(Number(v.toFixed(6)));
  }
  return out;
});

const yTicks = computed<number[]>(() => {
  // ~4 ticks on a 0..maxCount integer count axis.
  const m = maxCount.value;
  const target = 4;
  const rawStep = m / target;
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(rawStep, 1))));
  const norm = rawStep / pow;
  const niceStep = Math.max(
    1,
    Math.ceil((norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10) * pow),
  );
  const out: number[] = [];
  for (let v = 0; v <= m; v += niceStep) out.push(v);
  if (out[out.length - 1] !== m) out.push(m);
  return out;
});

function fmtX(v: number): string {
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(2);
}
</script>

<template>
  <div :style="{ marginTop: '8px' }">
    <svg
      :width="WIDTH"
      :height="HEIGHT"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      :style="{ maxWidth: '100%', height: 'auto' }"
    >
      <!-- X axis line -->
      <line
        :x1="PADDING.left"
        :x2="WIDTH - PADDING.right"
        :y1="HEIGHT - PADDING.bottom"
        :y2="HEIGHT - PADDING.bottom"
        stroke="#9ca3af"
        stroke-width="1"
      />
      <!-- Y axis line -->
      <line
        :x1="PADDING.left"
        :x2="PADDING.left"
        :y1="PADDING.top"
        :y2="HEIGHT - PADDING.bottom"
        stroke="#9ca3af"
        stroke-width="1"
      />

      <!-- X tick marks + labels -->
      <g v-for="t in xTicks" :key="`xt-${t}`">
        <line
          :x1="xFor(t)"
          :x2="xFor(t)"
          :y1="HEIGHT - PADDING.bottom"
          :y2="HEIGHT - PADDING.bottom + 4"
          stroke="#9ca3af"
          stroke-width="1"
        />
        <text
          :x="xFor(t)"
          :y="HEIGHT - PADDING.bottom + 18"
          font-size="11"
          fill="#374151"
          text-anchor="middle"
          font-family="system-ui, sans-serif"
        >
          {{ fmtX(t) }}
        </text>
      </g>

      <!-- Y tick marks + labels -->
      <g v-for="t in yTicks" :key="`yt-${t}`">
        <line
          :x1="PADDING.left - 4"
          :x2="PADDING.left"
          :y1="yForCount(t)"
          :y2="yForCount(t)"
          stroke="#9ca3af"
          stroke-width="1"
        />
        <text
          :x="PADDING.left - 6"
          :y="yForCount(t) + 4"
          font-size="11"
          fill="#374151"
          text-anchor="end"
          font-family="system-ui, sans-serif"
        >
          {{ t }}
        </text>
      </g>

      <!-- Bars -->
      <g>
        <rect
          v-for="(b, i) in bins"
          :key="`bin-${i}`"
          :x="xFor(b.x0)"
          :y="yForCount(b.count)"
          :width="Math.max(0, xFor(b.x1) - xFor(b.x0) - 1)"
          :height="Math.max(0, HEIGHT - PADDING.bottom - yForCount(b.count))"
          fill="#7da3d1"
          fill-opacity="0.85"
          stroke="#3b6fa0"
          stroke-width="0.5"
        >
          <title>
            {{ fmtX(b.x0) }} – {{ fmtX(b.x1) }}: {{ b.count }} clonotype{{
              b.count === 1 ? "" : "s"
            }}
          </title>
        </rect>
      </g>

      <!-- Threshold dashed lines (R54). Drawn on top of bars so the band
           edges remain visible. -->
      <g v-if="thresholds">
        <line
          v-for="(t, i) in thresholds"
          :key="`thr-${i}`"
          :x1="xFor(t.value)"
          :x2="xFor(t.value)"
          :y1="PADDING.top"
          :y2="HEIGHT - PADDING.bottom"
          :stroke="t.color ?? '#94a3b8'"
          stroke-width="1.5"
          stroke-dasharray="5 4"
        />
        <text
          v-for="(t, i) in thresholds"
          :key="`thr-l-${i}`"
          :x="xFor(t.value)"
          :y="PADDING.top - 6"
          font-size="10"
          :fill="t.color ?? '#64748b'"
          text-anchor="middle"
          font-family="system-ui, sans-serif"
        >
          {{ fmtX(t.value) }}
        </text>
      </g>

      <!-- Y axis title -->
      <text
        :x="PADDING.left - 26"
        :y="PADDING.top + PLOT_H / 2"
        font-size="10"
        fill="#6b7280"
        text-anchor="middle"
        font-family="system-ui, sans-serif"
        :transform="`rotate(-90, ${PADDING.left - 26}, ${PADDING.top + PLOT_H / 2})`"
      >
        Clonotype count
      </text>
    </svg>
    <p
      v-if="axisLabel"
      :style="{
        fontSize: '11px',
        color: '#6b7280',
        margin: '0',
        textAlign: 'center',
      }"
    >
      {{ axisLabel }}
    </p>
  </div>
</template>
