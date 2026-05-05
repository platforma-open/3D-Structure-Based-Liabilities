/**
 * Lookup tables shared across the PDB parser and visualization components.
 * Centralized here so that the chemistry conventions (which residues are
 * hydrophobic, what a backbone atom is, which colors map to which property)
 * are defined once and reused.
 */

/** PDB three-letter → one-letter amino acid codes (standard 20 only). */
export const ONE_LETTER: Record<string, string> = {
  ALA: "A",
  ARG: "R",
  ASN: "N",
  ASP: "D",
  CYS: "C",
  GLU: "E",
  GLN: "Q",
  GLY: "G",
  HIS: "H",
  ILE: "I",
  LEU: "L",
  LYS: "K",
  MET: "M",
  PHE: "F",
  PRO: "P",
  SER: "S",
  THR: "T",
  TRP: "W",
  TYR: "Y",
  VAL: "V",
};

/** Amino-acid one-letter code → chemistry class. Used to color sequence boxes. */
export const AA_CLASS: Record<string, "hyd" | "pol" | "acid" | "bas"> = {
  A: "hyd",
  I: "hyd",
  L: "hyd",
  M: "hyd",
  F: "hyd",
  W: "hyd",
  V: "hyd",
  P: "hyd",
  S: "pol",
  T: "pol",
  C: "pol",
  N: "pol",
  Q: "pol",
  Y: "pol",
  G: "pol",
  D: "acid",
  E: "acid",
  K: "bas",
  R: "bas",
  H: "bas",
};

/** Background colors for sequence boxes by chemistry class. */
export const AA_COLOR: Record<string, string> = {
  hyd: "rgba(245, 158, 11, 0.25)",
  pol: "rgba(20, 184, 166, 0.25)",
  acid: "rgba(244, 63, 94, 0.25)",
  bas: "rgba(59, 130, 246, 0.25)",
  other: "rgba(148, 163, 184, 0.25)",
};

/** Underline colors for sequence boxes by secondary-structure assignment. */
export const SS_COLOR: Record<string, string> = {
  H: "#ef4444",
  E: "#f59e0b",
  C: "transparent",
};

/** Backbone atom names expected in every standard amino acid. */
export const BACKBONE = ["N", "CA", "C", "O"];
