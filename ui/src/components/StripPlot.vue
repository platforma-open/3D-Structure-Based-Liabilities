<script setup lang="ts">
import { computed } from "vue";
import { fmtAxisValue, niceTicks } from "../utils/chart";

/**
 * Spec R54 — strip plot rendered below ~20 clonotypes where a histogram
 * collapses to a single tower. Each clonotype is a dot at its value on the
 * metric axis; Raybould 2019 / Gordon 2025 threshold values are drawn as
 * dashed vertical lines so the user can read each candidate's standing
 * directly. Pure SVG so it stays standalone and doesn't fight graph-maker's
 * histogram template, which currently ignores `pl7.app/graph/thresholds`.
 */
type Point = { key: string; value: number };
type Threshold = { value: number; color?: string };

const props = defineProps<{
  points: Point[];
  thresholds?: Threshold[];
  /** Plot subtitle / axis description. */
  axisLabel?: string;
}>();

// Plot uses fixed pixel dimensions. The Y axis is jittered (point index)
// so dots at identical x don't overlap; jitter amount is small enough that
// it stays visibly aligned to its value.
const PADDING = { top: 20, right: 24, bottom: 36, left: 24 };
const WIDTH = 760;
const HEIGHT = 220;
const PLOT_W = WIDTH - PADDING.left - PADDING.right;
const PLOT_H = HEIGHT - PADDING.top - PADDING.bottom;

const xDomain = computed(() => {
  const all: number[] = props.points.map((p) => p.value);
  if (props.thresholds) {
    for (const t of props.thresholds) all.push(t.value);
  }
  if (all.length === 0) return { min: 0, max: 1 };
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) {
    // Single-value collapse: pad ±10% so the dot sits in the middle.
    const pad = Math.abs(min) > 0 ? Math.abs(min) * 0.1 : 1;
    min -= pad;
    max += pad;
  } else {
    const pad = (max - min) * 0.08;
    min -= pad;
    max += pad;
  }
  return { min, max };
});

function xFor(value: number): number {
  const { min, max } = xDomain.value;
  return PADDING.left + ((value - min) / (max - min)) * PLOT_W;
}

function yFor(idx: number, total: number): number {
  // Spread dots vertically by index so identical x values stay readable;
  // single point sits in the middle.
  if (total <= 1) return PADDING.top + PLOT_H / 2;
  return PADDING.top + (idx / (total - 1)) * PLOT_H;
}

const ticks = computed<number[]>(() => niceTicks(xDomain.value.min, xDomain.value.max));

const sortedPoints = computed(() => [...props.points].sort((a, b) => a.value - b.value));
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
      <!-- Axis line -->
      <line
        :x1="PADDING.left"
        :x2="WIDTH - PADDING.right"
        :y1="HEIGHT - PADDING.bottom"
        :y2="HEIGHT - PADDING.bottom"
        stroke="#9ca3af"
        stroke-width="1"
      />

      <!-- Tick marks + labels -->
      <g v-for="t in ticks" :key="t">
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
          {{ fmtAxisValue(t) }}
        </text>
      </g>

      <!-- Threshold dashed lines (R54). Drawn behind the dots. -->
      <g v-if="thresholds">
        <line
          v-for="(t, i) in thresholds"
          :key="`thr-${i}`"
          :x1="xFor(t.value)"
          :x2="xFor(t.value)"
          :y1="PADDING.top"
          :y2="HEIGHT - PADDING.bottom"
          :stroke="t.color ?? '#94a3b8'"
          stroke-width="1"
          stroke-dasharray="4 4"
        />
        <text
          v-for="(t, i) in thresholds"
          :key="`thr-l-${i}`"
          :x="xFor(t.value)"
          :y="PADDING.top - 4"
          font-size="10"
          :fill="t.color ?? '#64748b'"
          text-anchor="middle"
          font-family="system-ui, sans-serif"
        >
          {{ fmtAxisValue(t.value) }}
        </text>
      </g>

      <!-- Data dots -->
      <g>
        <g v-for="(p, i) in sortedPoints" :key="p.key">
          <circle
            :cx="xFor(p.value)"
            :cy="yFor(i, sortedPoints.length)"
            r="5"
            fill="#3b82f6"
            fill-opacity="0.75"
            stroke="#1d4ed8"
            stroke-width="1"
          >
            <title>{{ p.key }}: {{ fmtAxisValue(p.value) }}</title>
          </circle>
          <text
            :x="xFor(p.value) + 8"
            :y="yFor(i, sortedPoints.length) + 4"
            font-size="11"
            fill="#1f2937"
            font-family="system-ui, sans-serif"
          >
            {{ p.key }}
          </text>
        </g>
      </g>
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
