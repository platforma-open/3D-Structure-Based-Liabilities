import type { DatasetSelection } from "@platforma-sdk/model";

/** Numbering schemes supported for region tagging. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

/** Dataset-level mode: paired Fv (TAP) or single-chain VHH (TNP). */
export type DetectedMode = "TAP" | "TNP";

/** Unified user-editable state persisted by the model. */
export type BlockData = {
  /** Predicted-structures dataset picked via `PlDatasetSelector`. */
  dataset?: DatasetSelection;
  /** Numbering scheme; empty string means unknown (neutral region weights). */
  numberingScheme: NumberingScheme | "";
  /** Manual heavy/light chain mapping, used only when a PDB carries no
   *  REMARK 99 PLATFORMA CDR records to auto-detect them. */
  heavyChainId: string;
  lightChainId: string;
  /** Confidence-gating thresholds (Å) for framework and CDR regions. */
  frConfThresh: number;
  cdrConfThresh: number;
  /** User-set block label; empty falls back to the derived default. */
  customBlockLabel: string;
};

/** Projection consumed by the workflow. */
export type BlockArgs = {
  primaryRef: NonNullable<DatasetSelection["primary"]>;
  numberingScheme: NumberingScheme | "";
  heavyChainId: string;
  lightChainId: string;
  frConfThresh: number;
  cdrConfThresh: number;
};
