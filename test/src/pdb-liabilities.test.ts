import { describe, expect, it } from "vitest";
import { parsePdb } from "../../ui/src/pdb/parser";
import {
  deamidationHotspots,
  glycosylationSequons,
  oxidationHotspots,
  unpairedCysteines,
} from "../../ui/src/pdb/liabilities";

const atomLine = (resName: string, chain: string, resSeq: number): string =>
  `ATOM      1  CA  ${resName.padEnd(3, " ")} ${chain}${String(resSeq).padStart(4, " ")}`.padEnd(
    80,
    " ",
  );

const ssbondLine = (chain1: string, res1: number, chain2: string, res2: number): string =>
  `SSBOND   1 CYS ${chain1} ${String(res1).padStart(4, " ")}    CYS ${chain2} ${String(res2).padStart(4, " ")}`.padEnd(
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

  it("captures SSBOND records", () => {
    const p = parsePdb(TEST_PDB);
    expect(p.ssbonds).toEqual([{ chain1: "A", res1: 10, chain2: "A", res2: 15 }]);
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
    expect(p.residuesByChain.get("A")).toEqual([{ resSeq: 1, resName: "ALA" }]);
  });
});

describe("unpairedCysteines", () => {
  it("flags Cys residues not in any SSBOND", () => {
    const hits = unpairedCysteines(parsePdb(TEST_PDB));
    expect(hits).toEqual([{ chainId: "A", resSeq: 2, resName: "CYS" }]);
  });
});

describe("deamidationHotspots", () => {
  it("flags N-G with motif='NG'", () => {
    const hits = deamidationHotspots(parsePdb(TEST_PDB));
    const ng = hits.find((h) => h.resSeq === 3);
    expect(ng).toMatchObject({ chainId: "A", resSeq: 3, motif: "NG" });
  });

  it("does not flag non-NG/NS dipeptides", () => {
    const pdb = [atomLine("ASN", "A", 1), atomLine("ALA", "A", 2)].join("\n");
    expect(deamidationHotspots(parsePdb(pdb))).toEqual([]);
  });

  it("respects sequence-numbering gaps", () => {
    const pdb = [atomLine("ASN", "A", 1), atomLine("GLY", "A", 5)].join("\n");
    expect(deamidationHotspots(parsePdb(pdb))).toEqual([]);
  });
});

describe("glycosylationSequons", () => {
  it("flags N-X-T motifs (X ≠ P)", () => {
    const hits = glycosylationSequons(parsePdb(TEST_PDB));
    const sequon = hits.find((h) => h.resSeq === 5);
    expect(sequon).toMatchObject({ chainId: "A", resSeq: 5, motif: "N-A-T" });
  });

  it("rejects sequons where X = P", () => {
    const pdb = [
      atomLine("ASN", "A", 1),
      atomLine("PRO", "A", 2),
      atomLine("SER", "A", 3),
    ].join("\n");
    expect(glycosylationSequons(parsePdb(pdb))).toEqual([]);
  });
});

describe("oxidationHotspots", () => {
  it("flags methionine and tryptophan positions", () => {
    const hits = oxidationHotspots(parsePdb(TEST_PDB));
    const codes = hits.map((h) => h.resName).sort();
    expect(codes).toEqual(["MET", "TRP"]);
  });
});
