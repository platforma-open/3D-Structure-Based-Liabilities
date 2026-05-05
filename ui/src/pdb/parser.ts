/**
 * Streaming, single-pass parser for PDB-format files.
 *
 * Walks each line once, dispatches on the first six columns (the record name),
 * and extracts fields by column slice per the PDB v3.3 spec. Returns a
 * `Parsed` value that downstream pure derivations and Vue components consume.
 *
 * Multi-MODEL files: only the FIRST MODEL's atoms populate the per-residue
 * data, but the total `models` count is tracked so the UI can disclose it.
 *
 * Robustness notes:
 *  - Lines shorter than 80 columns are right-padded so column-based slicing
 *    never reads past end-of-line.
 *  - Numeric fields use {@link tryNum} which returns `null` on parse failure;
 *    callers default `null` → `0` where a numeric is required.
 *  - `element` falls back to the first 1–2 non-digit characters of the atom
 *    name when columns 76–78 are blank (older or non-canonical PDBs).
 */

/** A single ATOM/HETATM record, fully extracted. */
export type Atom = {
  name: string;
  altLoc: string;
  resName: string;
  chainId: string;
  resSeq: number;
  iCode: string;
  x: number;
  y: number;
  z: number;
  bFactor: number;
  element: string;
  isHet: boolean;
};

/** A residue is the group of atoms sharing (chain, resSeq, iCode). */
export type Residue = {
  chainId: string;
  resSeq: number;
  resName: string;
  atoms: Atom[];
};

export type Helix = { chainId: string; startSeq: number; endSeq: number };
export type Sheet = { chainId: string; startSeq: number; endSeq: number };
export type Ssbond = { chain1: string; res1: number; chain2: string; res2: number };
export type Modres = {
  resName: string;
  stdName: string;
  chainId: string;
  resSeq: number;
  comment: string;
};

/** Crystal unit cell from the CRYST1 record. */
export type Cryst = {
  a: number;
  b: number;
  c: number;
  alpha: number;
  beta: number;
  gamma: number;
  spaceGroup: string;
};

/** Top-level parse result — the only shape downstream code should depend on. */
export type Parsed = {
  header: string;
  title: string;
  experimentalMethod: string;
  resolution: number | null;
  rFactor: number | null;
  rFree: number | null;
  cryst: Cryst | null;
  models: number;
  atomCount: number;
  hetatmCount: number;
  altLocs: Set<string>;
  chainOrder: string[];
  residuesByChain: Map<string, Residue[]>;
  helices: Helix[];
  sheets: Sheet[];
  ssbonds: Ssbond[];
  modres: Modres[];
};

/** Parse a fixed-width numeric field; returns null when the slice isn't a finite number. */
const tryNum = (s: string): number | null => {
  const v = parseFloat(s);
  return Number.isFinite(v) ? v : null;
};

export function parsePdb(text: string): Parsed {
  const out: Parsed = {
    header: "",
    title: "",
    experimentalMethod: "",
    resolution: null,
    rFactor: null,
    rFree: null,
    cryst: null,
    models: 0,
    atomCount: 0,
    hetatmCount: 0,
    altLocs: new Set(),
    chainOrder: [],
    residuesByChain: new Map(),
    helices: [],
    sheets: [],
    ssbonds: [],
    modres: [],
  };
  const titleParts: string[] = [];
  const expdtaParts: string[] = [];
  const resByKey = new Map<string, Residue>();
  let inFirstModel = true;

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.padEnd(80, " ");
    const tag = line.slice(0, 6).trimEnd();

    if (tag === "HEADER") out.header = line.slice(10, 50).trim();
    else if (tag === "TITLE") titleParts.push(line.slice(10, 80).trim());
    else if (tag === "EXPDTA") expdtaParts.push(line.slice(10, 80).trim());
    else if (tag === "MODEL") {
      out.models += 1;
      if (out.models > 1) inFirstModel = false;
    } else if (tag === "REMARK") {
      const num = parseInt(line.slice(7, 10).trim(), 10);
      const body = line.slice(11);
      if (num === 2 && body.includes("RESOLUTION")) {
        const m = body.match(/(\d+\.\d+)/);
        if (m) out.resolution = parseFloat(m[1]);
      } else if (num === 3) {
        const m1 = body.match(/R VALUE\s*\(WORKING SET\)\s*:\s*([\d.]+)/i);
        const m2 = body.match(/FREE R VALUE\s*:\s*([\d.]+)/i);
        if (m1) out.rFactor = parseFloat(m1[1]);
        if (m2) out.rFree = parseFloat(m2[1]);
      }
    } else if (tag === "CRYST1") {
      out.cryst = {
        a: tryNum(line.slice(6, 15)) ?? 0,
        b: tryNum(line.slice(15, 24)) ?? 0,
        c: tryNum(line.slice(24, 33)) ?? 0,
        alpha: tryNum(line.slice(33, 40)) ?? 0,
        beta: tryNum(line.slice(40, 47)) ?? 0,
        gamma: tryNum(line.slice(47, 54)) ?? 0,
        spaceGroup: line.slice(55, 66).trim(),
      };
    } else if (tag === "HELIX") {
      const chainId = line.slice(19, 20);
      const startSeq = parseInt(line.slice(21, 25).trim(), 10);
      const endSeq = parseInt(line.slice(33, 37).trim(), 10);
      if (Number.isFinite(startSeq) && Number.isFinite(endSeq))
        out.helices.push({ chainId, startSeq, endSeq });
    } else if (tag === "SHEET") {
      const chainId = line.slice(21, 22);
      const startSeq = parseInt(line.slice(22, 26).trim(), 10);
      const endSeq = parseInt(line.slice(33, 37).trim(), 10);
      if (Number.isFinite(startSeq) && Number.isFinite(endSeq))
        out.sheets.push({ chainId, startSeq, endSeq });
    } else if (tag === "SSBOND") {
      const chain1 = line.slice(15, 16);
      const res1 = parseInt(line.slice(17, 21).trim(), 10);
      const chain2 = line.slice(29, 30);
      const res2 = parseInt(line.slice(31, 35).trim(), 10);
      if (Number.isFinite(res1) && Number.isFinite(res2))
        out.ssbonds.push({ chain1, res1, chain2, res2 });
    } else if (tag === "MODRES") {
      out.modres.push({
        resName: line.slice(12, 15).trim(),
        chainId: line.slice(16, 17),
        resSeq: parseInt(line.slice(18, 22).trim(), 10),
        stdName: line.slice(24, 27).trim(),
        comment: line.slice(29, 70).trim(),
      });
    } else if (tag === "ATOM" || tag === "HETATM") {
      if (!inFirstModel) continue;
      const isHet = tag === "HETATM";
      if (isHet) out.hetatmCount += 1;
      else out.atomCount += 1;
      const name = line.slice(12, 16).trim();
      const altLoc = line.slice(16, 17).trim();
      const resName = line.slice(17, 20).trim();
      const chainId = line.slice(21, 22) || " ";
      const resSeq = parseInt(line.slice(22, 26).trim(), 10);
      const iCode = line.slice(26, 27).trim();
      const x = tryNum(line.slice(30, 38)) ?? 0;
      const y = tryNum(line.slice(38, 46)) ?? 0;
      const z = tryNum(line.slice(46, 54)) ?? 0;
      const bFactor = tryNum(line.slice(60, 66)) ?? 0;
      const element = (
        line.slice(76, 78).trim() || name.replace(/\d/g, "").slice(0, 2)
      ).toUpperCase();
      if (altLoc) out.altLocs.add(altLoc);
      const atom: Atom = {
        name,
        altLoc,
        resName,
        chainId,
        resSeq,
        iCode,
        x,
        y,
        z,
        bFactor,
        element,
        isHet,
      };
      const key = `${chainId}|${resSeq}|${iCode}`;
      let res = resByKey.get(key);
      if (!res) {
        res = { chainId, resSeq, resName, atoms: [] };
        resByKey.set(key, res);
        if (!out.residuesByChain.has(chainId)) {
          out.residuesByChain.set(chainId, []);
          out.chainOrder.push(chainId);
        }
        out.residuesByChain.get(chainId)!.push(res);
      }
      res.atoms.push(atom);
    }
  }
  out.title = titleParts.join(" ").replace(/\s+/g, " ").trim();
  out.experimentalMethod = expdtaParts.join(" ").replace(/\s+/g, " ").trim();
  return out;
}
