/**
 * Sequence-based liability detection for therapeutic-antibody developability.
 *
 * Each function in this module scans a {@link Parsed} PDB and returns a list
 * of {@link LiabilityHit} records — one per flagged residue or motif. These
 * are pure, side-effect-free, and match the same shape so they can all be
 * rendered by the same `PdbLiabilityList` component.
 *
 * **Important caveats — these detectors are sequence-only.** Real
 * developability assessment also requires solvent-accessible surface area
 * (SASA) to filter for surface-exposed hits, plus antibody numbering
 * (Kabat/Chothia/IMGT) to know which hits fall in CDRs vs. framework. Both
 * are out of scope for this pass; everything here flags by sequence motif
 * regardless of structural exposure or antibody region.
 */
import { ONE_LETTER } from "./constants";
import type { Parsed } from "./parser";

export type LiabilityHit = {
  chainId: string;
  resSeq: number;
  /** 3-letter residue code at the hit position. */
  resName: string;
  /** Sequence motif when applicable (e.g. "NG", "N-X-T"). */
  motif?: string;
  /** Original 3-letter codes that produced the motif (e.g. "ASN-GLY"). */
  context?: string;
};

/**
 * Cysteines NOT participating in any SSBOND record. Free Cys are a
 * developability liability: they can form intermolecular disulfides during
 * production, drive aggregation, or be attacked by free thiols/oxidants.
 *
 * Implementation: build a set of (chain, resSeq) keys appearing in any
 * SSBOND endpoint, then iterate every CYS residue and emit a hit when the
 * key isn't in the set.
 */
export function unpairedCysteines(parsed: Parsed): LiabilityHit[] {
  const bonded = new Set<string>();
  for (const b of parsed.ssbonds) {
    bonded.add(`${b.chain1}|${b.res1}`);
    bonded.add(`${b.chain2}|${b.res2}`);
  }
  const out: LiabilityHit[] = [];
  for (const id of parsed.chainOrder) {
    for (const r of parsed.residuesByChain.get(id)!) {
      if (r.resName === "CYS" && !bonded.has(`${id}|${r.resSeq}`)) {
        out.push({ chainId: id, resSeq: r.resSeq, resName: "CYS" });
      }
    }
  }
  return out;
}

/**
 * Asparagine deamidation hotspots: N-G and N-S dipeptide motifs in the
 * primary sequence. The asparagine spontaneously deamidates to aspartate
 * (or iso-aspartate) over time, especially when followed by glycine — which
 * has the highest published rate constant. N-S is medium risk.
 *
 * Only flags when the two residues are CONSECUTIVE in the structure (no
 * sequence-numbering gap), since a gap means we're crossing a missing-loop
 * region where the dipeptide isn't actually adjacent.
 */
export function deamidationHotspots(parsed: Parsed): LiabilityHit[] {
  const out: LiabilityHit[] = [];
  for (const id of parsed.chainOrder) {
    const residues = parsed.residuesByChain.get(id)!;
    for (let i = 0; i < residues.length - 1; i++) {
      const a = residues[i];
      const b = residues[i + 1];
      if (b.resSeq - a.resSeq !== 1) continue;
      if (a.resName !== "ASN") continue;
      if (b.resName !== "GLY" && b.resName !== "SER") continue;
      const motif = (ONE_LETTER[a.resName] ?? "?") + (ONE_LETTER[b.resName] ?? "?");
      out.push({
        chainId: id,
        resSeq: a.resSeq,
        resName: "ASN",
        motif,
        context: `${a.resName}-${b.resName}`,
      });
    }
  }
  return out;
}

/**
 * N-linked glycosylation sequons: the consensus N-X-[S/T] where X is any
 * residue except proline. When exposed and in the right structural context
 * these are recognized by oligosaccharyltransferase in the ER, leading to
 * N-glycan attachment — a major developability concern when it lands in a
 * CDR or near an antigen-binding site.
 *
 * Only flags when all three residues are CONSECUTIVE in the structure (no
 * gaps), so sequons that cross unresolved loops aren't reported.
 */
export function glycosylationSequons(parsed: Parsed): LiabilityHit[] {
  const out: LiabilityHit[] = [];
  for (const id of parsed.chainOrder) {
    const residues = parsed.residuesByChain.get(id)!;
    for (let i = 0; i < residues.length - 2; i++) {
      const a = residues[i];
      const b = residues[i + 1];
      const c = residues[i + 2];
      if (b.resSeq - a.resSeq !== 1) continue;
      if (c.resSeq - b.resSeq !== 1) continue;
      if (a.resName !== "ASN") continue;
      if (b.resName === "PRO") continue;
      if (c.resName !== "SER" && c.resName !== "THR") continue;
      const X = ONE_LETTER[b.resName] ?? "X";
      const T = ONE_LETTER[c.resName] ?? "?";
      out.push({
        chainId: id,
        resSeq: a.resSeq,
        resName: "ASN",
        motif: `N-${X}-${T}`,
        context: `${a.resName}-${b.resName}-${c.resName}`,
      });
    }
  }
  return out;
}

/**
 * Sequence-level oxidation hotspots: methionine (M) and tryptophan (W)
 * residues. Both side chains are oxidation-prone; M oxidizes to methionine
 * sulfoxide under formulation stress, W to kynurenine / N-formyl-kynurenine
 * under photo-oxidation.
 *
 * NOTE: this is the unfiltered sequence list. Real-world oxidation risk
 * depends on solvent exposure (a buried Met is generally safe). When SASA
 * is added in chunk 2, this list should be filtered to surface-exposed
 * residues.
 */
export function oxidationHotspots(parsed: Parsed): LiabilityHit[] {
  const out: LiabilityHit[] = [];
  for (const id of parsed.chainOrder) {
    for (const r of parsed.residuesByChain.get(id)!) {
      if (r.resName === "MET" || r.resName === "TRP") {
        out.push({ chainId: id, resSeq: r.resSeq, resName: r.resName });
      }
    }
  }
  return out;
}
