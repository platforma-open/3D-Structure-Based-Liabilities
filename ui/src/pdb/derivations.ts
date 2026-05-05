/**
 * Pure derivations from a {@link Parsed} PDB. Each function takes the parser
 * output and produces a single, presentation-ready data shape that one
 * visualization component consumes.
 *
 * These are intentionally:
 *  - **side-effect-free** so they can be wrapped in Vue `computed()` or unit-
 *    tested directly,
 *  - **independent of each other** unless one trivially reuses another's
 *    output (e.g., `sequences` reads `ssByChain`),
 *  - **typed end-to-end** so component props can refer to the same types.
 */
import { AA_CLASS, BACKBONE, ONE_LETTER } from "./constants";
import type { Parsed } from "./parser";

export type ChainStat = { id: string; residues: number; atoms: number };
export type CountEntry = { key: string; count: number };
export type Bounds = {
  dx: number;
  dy: number;
  dz: number;
  cx: number;
  cy: number;
  cz: number;
};
export type SsAssign = "H" | "E" | "C";
export type SsCounts = {
  h: number;
  e: number;
  c: number;
  total: number;
  pctH: number;
  pctE: number;
  pctC: number;
};
export type SequenceLetter = {
  letter: string;
  cls: string;
  ss: SsAssign;
  resName: string;
  resSeq: number;
};
export type SequenceChain = { id: string; letters: SequenceLetter[] };
export type ValidationRow = { id: string; missing: number; gaps: number; altLocs: number };
export type BFactorProfile = { values: number[]; max: number };
export type ContactMap = {
  chainId: string;
  n: number;
  matrix: Float32Array;
  stride: number;
};

/** Per-chain residue and atom counts, in chain-discovery order. */
export function chainSummary(parsed: Parsed): ChainStat[] {
  return parsed.chainOrder.map((id) => {
    const residues = parsed.residuesByChain.get(id)!;
    const atoms = residues.reduce((n, r) => n + r.atoms.length, 0);
    return { id, residues: residues.length, atoms };
  });
}

/** Atom counts grouped by 3-letter residue code, sorted descending. */
export function residueTypes(parsed: Parsed): CountEntry[] {
  const m = new Map<string, number>();
  for (const residues of parsed.residuesByChain.values())
    for (const r of residues) m.set(r.resName, (m.get(r.resName) ?? 0) + r.atoms.length);
  return [...m.entries()].map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
}

/** Atom counts grouped by element symbol, sorted descending. */
export function elements(parsed: Parsed): CountEntry[] {
  const m = new Map<string, number>();
  for (const residues of parsed.residuesByChain.values())
    for (const r of residues)
      for (const a of r.atoms) m.set(a.element, (m.get(a.element) ?? 0) + 1);
  return [...m.entries()].map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
}

/** Flat list of every atom's B-factor — feeds the histogram. */
export function allBFactors(parsed: Parsed): number[] {
  const arr: number[] = [];
  for (const residues of parsed.residuesByChain.values())
    for (const r of residues) for (const a of r.atoms) arr.push(a.bFactor);
  return arr;
}

/** Bounding-box deltas (dx, dy, dz) and centroid (cx, cy, cz) over all atoms. */
export function bounds(parsed: Parsed): Bounds | null {
  let minX = Infinity,
    minY = Infinity,
    minZ = Infinity;
  let maxX = -Infinity,
    maxY = -Infinity,
    maxZ = -Infinity;
  let sx = 0,
    sy = 0,
    sz = 0,
    n = 0;
  for (const residues of parsed.residuesByChain.values())
    for (const r of residues)
      for (const a of r.atoms) {
        if (a.x < minX) minX = a.x;
        if (a.x > maxX) maxX = a.x;
        if (a.y < minY) minY = a.y;
        if (a.y > maxY) maxY = a.y;
        if (a.z < minZ) minZ = a.z;
        if (a.z > maxZ) maxZ = a.z;
        sx += a.x;
        sy += a.y;
        sz += a.z;
        n += 1;
      }
  if (!n) return null;
  return {
    dx: maxX - minX,
    dy: maxY - minY,
    dz: maxZ - minZ,
    cx: sx / n,
    cy: sy / n,
    cz: sz / n,
  };
}

/**
 * Per-residue secondary-structure assignment per chain, in residue order.
 * Driven by HELIX and SHEET records — residues outside any annotated range
 * are treated as coil ("C"). HELIX overlaps SHEET wins last-writer.
 */
export function ssByChain(parsed: Parsed): Map<string, SsAssign[]> {
  const out = new Map<string, SsAssign[]>();
  for (const chainId of parsed.chainOrder) {
    const residues = parsed.residuesByChain.get(chainId)!;
    const arr: SsAssign[] = residues.map(() => "C");
    for (const h of parsed.helices) {
      if (h.chainId !== chainId) continue;
      residues.forEach((r, i) => {
        if (r.resSeq >= h.startSeq && r.resSeq <= h.endSeq) arr[i] = "H";
      });
    }
    for (const s of parsed.sheets) {
      if (s.chainId !== chainId) continue;
      residues.forEach((r, i) => {
        if (r.resSeq >= s.startSeq && r.resSeq <= s.endSeq) arr[i] = "E";
      });
    }
    out.set(chainId, arr);
  }
  return out;
}

/** Aggregate helix/sheet/coil counts and percentages across the whole structure. */
export function ssCounts(ss: Map<string, SsAssign[]>): SsCounts {
  let h = 0,
    e = 0,
    c = 0;
  for (const arr of ss.values())
    for (const v of arr) {
      if (v === "H") h += 1;
      else if (v === "E") e += 1;
      else c += 1;
    }
  const total = h + e + c || 1;
  return {
    h,
    e,
    c,
    total,
    pctH: (h / total) * 100,
    pctE: (e / total) * 100,
    pctC: (c / total) * 100,
  };
}

/**
 * Per-chain 1-letter sequence with chemistry class and secondary-structure
 * annotation per residue. Non-standard residues collapse to "·".
 */
export function sequences(parsed: Parsed, ss: Map<string, SsAssign[]>): SequenceChain[] {
  return parsed.chainOrder.map((id) => {
    const residues = parsed.residuesByChain.get(id)!;
    const ssArr = ss.get(id) ?? [];
    return {
      id,
      letters: residues.map((r, i) => {
        const letter = ONE_LETTER[r.resName] ?? "·";
        const cls = AA_CLASS[letter] ?? "other";
        return { letter, cls, ss: ssArr[i] ?? "C", resName: r.resName, resSeq: r.resSeq };
      }),
    };
  });
}

/**
 * Per-chain validation flags:
 *  - `missing`: residues with at least one of N/CA/C/O absent.
 *  - `gaps`: jumps > 1 in the residue numbering between adjacent residues.
 *  - `altLocs`: count of distinct alt-loc labels present in the chain.
 */
export function validation(parsed: Parsed): ValidationRow[] {
  return parsed.chainOrder.map((id) => {
    const residues = parsed.residuesByChain.get(id)!;
    let missing = 0,
      gaps = 0;
    for (const r of residues) {
      if (!(r.resName in ONE_LETTER)) continue;
      const names = new Set(r.atoms.map((a) => a.name));
      if (!BACKBONE.every((b) => names.has(b))) missing += 1;
    }
    for (let i = 1; i < residues.length; i++) {
      if (residues[i].resSeq - residues[i - 1].resSeq > 1) gaps += 1;
    }
    const altLocs = new Set<string>();
    for (const r of residues) for (const a of r.atoms) if (a.altLoc) altLocs.add(a.altLoc);
    return { id, missing, gaps, altLocs: altLocs.size };
  });
}

/** Per-chain mean B-factor per residue (averaged over the residue's atoms). */
export function bFactorByChain(parsed: Parsed): Map<string, BFactorProfile> {
  const out = new Map<string, BFactorProfile>();
  for (const id of parsed.chainOrder) {
    const residues = parsed.residuesByChain.get(id)!;
    const values = residues.map((r) =>
      r.atoms.length ? r.atoms.reduce((s, a) => s + a.bFactor, 0) / r.atoms.length : 0,
    );
    const max = values.reduce((m, v) => (v > m ? v : m), 0) || 1;
    out.set(id, { values, max });
  }
  return out;
}

/**
 * Pairwise CA-CA distance matrix for the largest chain, downsampled to at
 * most 200 rows/cols so very large structures still render quickly. The full
 * symmetric `n × n` matrix is stored in a Float32Array for canvas blitting.
 */
export function contactMap(parsed: Parsed): ContactMap | null {
  const sorted = [...parsed.chainOrder]
    .map((id) => ({ id, residues: parsed.residuesByChain.get(id)! }))
    .sort((a, b) => b.residues.length - a.residues.length);
  if (!sorted.length) return null;
  const target = sorted[0];
  const cas: { x: number; y: number; z: number }[] = [];
  for (const r of target.residues) {
    const ca = r.atoms.find((a) => a.name === "CA");
    if (ca) cas.push({ x: ca.x, y: ca.y, z: ca.z });
  }
  if (!cas.length) return null;
  let stride = 1;
  if (cas.length > 200) stride = Math.ceil(cas.length / 200);
  const sample = cas.filter((_, i) => i % stride === 0);
  const n = sample.length;
  const matrix = new Float32Array(n * n);
  for (let i = 0; i < n; i++)
    for (let j = i; j < n; j++) {
      const dx = sample[i].x - sample[j].x;
      const dy = sample[i].y - sample[j].y;
      const dz = sample[i].z - sample[j].z;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      matrix[i * n + j] = d;
      matrix[j * n + i] = d;
    }
  return { chainId: target.id, n, matrix, stride };
}
