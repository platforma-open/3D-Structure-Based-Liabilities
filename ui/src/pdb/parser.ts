/**
 * Minimal PDB parser. Walks each line once and extracts only what the
 * liability detectors consume:
 *
 *  - ATOM / HETATM → identifies unique residues per chain
 *    (keyed by chain ID + sequence number + insertion code).
 *  - SSBOND      → list of disulfide pairs.
 *  - MODEL       → only the first MODEL block contributes residues; later
 *                  models are ignored.
 *
 * Everything else (HEADER, TITLE, REMARK, CRYST1, HELIX, SHEET, MODRES,
 * coordinates, B-factors, alt-locs, elements) is intentionally NOT parsed.
 * If a future liability detector needs that data, restore the relevant
 * branch from git history.
 */

/** A residue identified by sequence number and 3-letter code. */
export type Residue = { resSeq: number; resName: string };

/** A disulfide bond from an SSBOND record. */
export type Ssbond = { chain1: string; res1: number; chain2: string; res2: number };

/** Top-level parse result — the only shape downstream code depends on. */
export type Parsed = {
  chainOrder: string[];
  residuesByChain: Map<string, Residue[]>;
  ssbonds: Ssbond[];
};

export function parsePdb(text: string): Parsed {
  const out: Parsed = {
    chainOrder: [],
    residuesByChain: new Map(),
    ssbonds: [],
  };
  const seen = new Set<string>();
  let inFirstModel = true;
  let modelCount = 0;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.padEnd(80, " ");
    const tag = line.slice(0, 6).trimEnd();

    if (tag === "MODEL") {
      modelCount += 1;
      if (modelCount > 1) inFirstModel = false;
    } else if (tag === "SSBOND") {
      const chain1 = line.slice(15, 16);
      const res1 = parseInt(line.slice(17, 21).trim(), 10);
      const chain2 = line.slice(29, 30);
      const res2 = parseInt(line.slice(31, 35).trim(), 10);
      if (Number.isFinite(res1) && Number.isFinite(res2))
        out.ssbonds.push({ chain1, res1, chain2, res2 });
    } else if (tag === "ATOM" || tag === "HETATM") {
      if (!inFirstModel) continue;
      const resName = line.slice(17, 20).trim();
      const chainId = line.slice(21, 22) || " ";
      const resSeq = parseInt(line.slice(22, 26).trim(), 10);
      const iCode = line.slice(26, 27).trim();
      if (!Number.isFinite(resSeq)) continue;
      const key = `${chainId}|${resSeq}|${iCode}`;
      if (seen.has(key)) continue;
      seen.add(key);
      if (!out.residuesByChain.has(chainId)) {
        out.residuesByChain.set(chainId, []);
        out.chainOrder.push(chainId);
      }
      out.residuesByChain.get(chainId)!.push({ resSeq, resName });
    }
  }
  return out;
}
