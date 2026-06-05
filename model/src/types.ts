import type { DatasetSelection } from "@platforma-sdk/model";

/** Numbering schemes the runtime can interpret. The block is now hardcoded
 *  to IMGT at the workflow layer because every supported upstream emits
 *  IMGT-numbered structures; the type stays exported for downstream blocks
 *  that read the spec annotations. */
export type NumberingScheme = "imgt" | "chothia" | "kabat";

/** Dataset-level mode: paired Fv (TAP) or single-chain VHH (TNP). */
export type DetectedMode = "TAP" | "TNP";

/** Unified user-editable state persisted by the model. */
export type BlockData = {
  /** Predicted-structures dataset picked via `PlDatasetSelector`. */
  dataset?: DatasetSelection;
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
  heavyChainId: string;
  lightChainId: string;
  frConfThresh: number;
  cdrConfThresh: number;
};
