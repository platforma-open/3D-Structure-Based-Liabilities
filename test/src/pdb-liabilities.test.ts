import { describe, expect, it } from "vitest";
import { parsePdb } from "../../ui/src/pdb/parser";
import {
  deamidationHotspots,
  glycosylationSequons,
  oxidationHotspots,
  unpairedCysteines,
} from "../../ui/src/pdb/liabilities";

const atomLine = (resName: string, chain: string, resSeq: number, iCode = " "): string =>
  `ATOM      1  CA  ${resName.padEnd(3, " ")} ${chain}${String(resSeq).padStart(4, " ")}${iCode}`.padEnd(
    80,
    " ",
  );

const ssbondLine = (
  chain1: string,
  res1: number,
  chain2: string,
  res2: number,
  iCode1 = " ",
  iCode2 = " ",
): string =>
  `SSBOND   1 CYS ${chain1} ${String(res1).padStart(4, " ")}${iCode1}   CYS ${chain2} ${String(res2).padStart(4, " ")}${iCode2}`.padEnd(
    80,
    " ",
  );

// Synthetic single-chain PDB covering one example of each liability class.
const TEST_PDB = [
  atomLine("ALA", "A", 1),
  atomLine("CYS", "A", 2), // unpaired Cys (not in SSBOND below)
  atomLine("ASN", "A", 3), // deamidation NG → ASN at 3
  atomLine("GLY", "A", 4),
  atomLine("ASN", "A", 5), // glycosylation sequon N-A-T → ASN at 5
  atomLine("ALA", "A", 6),
  atomLine("THR", "A", 7),
  atomLine("MET", "A", 8), // oxidation hotspot
  atomLine("TRP", "A", 9), // oxidation hotspot
  atomLine("CYS", "A", 10), // paired (with 15)
  atomLine("ALA", "A", 11),
  atomLine("ALA", "A", 12),
  atomLine("ALA", "A", 13),
  atomLine("ALA", "A", 14),
  atomLine("CYS", "A", 15), // paired (with 10)
  ssbondLine("A", 10, "A", 15),
].join("\n");

describe("parsePdb", () => {
  it("collects unique residues per chain", () => {
    const p = parsePdb(TEST_PDB);
    expect(p.chainOrder).toEqual(["A"]);
    expect(p.residuesByChain.get("A")).toHaveLength(15);
  });

  it("captures SSBOND records with insertion codes", () => {
    const p = parsePdb(TEST_PDB);
    expect(p.ssbonds).toEqual([
      { chain1: "A", res1: 10, iCode1: "", chain2: "A", res2: 15, iCode2: "" },
    ]);
  });

  it("returns an empty parse for empty input", () => {
    const p = parsePdb("");
    expect(p.chainOrder).toEqual([]);
    expect(p.ssbonds).toEqual([]);
  });

  it("ignores atoms beyond the first MODEL block", () => {
    const pdb = [
      "MODEL        1".padEnd(80, " "),
      atomLine("ALA", "A", 1),
      "ENDMDL".padEnd(80, " "),
      "MODEL        2".padEnd(80, " "),
      atomLine("CYS", "A", 99),
      "ENDMDL".padEnd(80, " "),
    ].join("\n");
    const p = parsePdb(pdb);
    expect(p.residuesByChain.get("A")).toEqual([{ resSeq: 1, iCode: "", resName: "ALA" }]);
  });

  it("treats residues with the same resSeq but different iCode as distinct", () => {
    // Antibody-numbering case: 100, 100A, 100B in CDR3 — all must survive.
    const pdb = [
      atomLine("CYS", "H", 100),
      atomLine("ALA", "H", 100, "A"),
      atomLine("VAL", "H", 100, "B"),
    ].join("\n");
    const p = parsePdb(pdb);
    expect(p.residuesByChain.get("H")).toEqual([
      { resSeq: 100, iCode: "", resName: "CYS" },
      { resSeq: 100, iCode: "A", resName: "ALA" },
      { resSeq: 100, iCode: "B", resName: "VAL" },
    ]);
  });
});

describe("unpairedCysteines", () => {
  it("flags Cys residues not in any SSBOND", () => {
    const hits = unpairedCysteines(parsePdb(TEST_PDB));
    expect(hits).toEqual([{ chainId: "A", resSeq: 2, iCode: "", resName: "CYS" }]);
  });

  it("matches SSBOND endpoints by iCode (e.g. CYS 100 vs CYS 100A)", () => {
    const pdb = [
      atomLine("CYS", "A", 100),
      atomLine("ALA", "A", 101),
      atomLine("CYS", "A", 100, "A"),
      // SSBOND only links 100 (no iCode) and 200 — so 100A must remain unpaired.
      atomLine("CYS", "A", 200),
      ssbondLine("A", 100, "A", 200),
    ].join("\n");
    const hits = unpairedCysteines(parsePdb(pdb));
    expect(hits).toEqual([{ chainId: "A", resSeq: 100, iCode: "A", resName: "CYS" }]);
  });
});

describe("deamidationHotspots", () => {
  it("flags N-G with motif='NG'", () => {
    const hits = deamidationHotspots(parsePdb(TEST_PDB));
    const ng = hits.find((h) => h.resSeq === 3);
    expect(ng).toMatchObject({ chainId: "A", resSeq: 3, iCode: "", motif: "NG" });
  });

  it("does not flag non-NG/NS dipeptides", () => {
    const pdb = [atomLine("ASN", "A", 1), atomLine("ALA", "A", 2)].join("\n");
    expect(deamidationHotspots(parsePdb(pdb))).toEqual([]);
  });

  it("respects sequence-numbering gaps", () => {
    const pdb = [atomLine("ASN", "A", 1), atomLine("GLY", "A", 5)].join("\n");
    expect(deamidationHotspots(parsePdb(pdb))).toEqual([]);
  });

  it("flags N-G across an insertion-code boundary (100, 100A)", () => {
    const pdb = [atomLine("ASN", "H", 100), atomLine("GLY", "H", 100, "A")].join("\n");
    const hits = deamidationHotspots(parsePdb(pdb));
    expect(hits).toEqual([
      {
        chainId: "H",
        resSeq: 100,
        iCode: "",
        resName: "ASN",
        motif: "NG",
        context: "ASN-GLY",
      },
    ]);
  });
});

describe("glycosylationSequons", () => {
  it("flags N-X-T motifs (X ≠ P)", () => {
    const hits = glycosylationSequons(parsePdb(TEST_PDB));
    const sequon = hits.find((h) => h.resSeq === 5);
    expect(sequon).toMatchObject({ chainId: "A", resSeq: 5, iCode: "", motif: "N-A-T" });
  });

  it("rejects sequons where X = P", () => {
    const pdb = [
      atomLine("ASN", "A", 1),
      atomLine("PRO", "A", 2),
      atomLine("SER", "A", 3),
    ].join("\n");
    expect(glycosylationSequons(parsePdb(pdb))).toEqual([]);
  });

  it("flags an N-A-T sequon spanning insertion codes (100, 100A, 100B)", () => {
    const pdb = [
      atomLine("ASN", "H", 100),
      atomLine("ALA", "H", 100, "A"),
      atomLine("THR", "H", 100, "B"),
    ].join("\n");
    const hits = glycosylationSequons(parsePdb(pdb));
    expect(hits).toEqual([
      {
        chainId: "H",
        resSeq: 100,
        iCode: "",
        resName: "ASN",
        motif: "N-A-T",
        context: "ASN-ALA-THR",
      },
    ]);
  });
});

describe("oxidationHotspots", () => {
  it("flags methionine and tryptophan positions", () => {
    const hits = oxidationHotspots(parsePdb(TEST_PDB));
    const codes = hits.map((h) => h.resName).sort();
    expect(codes).toEqual(["MET", "TRP"]);
  });

  it("preserves iCode in emitted hits", () => {
    const pdb = [atomLine("MET", "A", 100, "A"), atomLine("TRP", "A", 100, "B")].join("\n");
    const hits = oxidationHotspots(parsePdb(pdb));
    expect(hits).toEqual([
      { chainId: "A", resSeq: 100, iCode: "A", resName: "MET" },
      { chainId: "A", resSeq: 100, iCode: "B", resName: "TRP" },
    ]);
  });
});
