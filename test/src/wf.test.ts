import { blockTest } from "@platforma-sdk/test";
import { blockSpec } from "this-block";

/**
 * Block-load sanity test. Adds the block to a fresh project and verifies
 * it loads without crashing. Does not run the workflow (the PrimaryRef
 * path needs an upstream `pl7.app/structure/pdb` ResourceMap, which means
 * a full 3D Structure Prediction block harness, out of scope for a unit
 * test).
 *
 * A proper end-to-end integration test would:
 *   1. Add a Samples & Data block + load a single-cell clonotype dataset.
 *   2. Add a MiXCR Clonotyping block + run it.
 *   3. Add the 3D Structure Prediction block + run it against a 1 to 3
 *      clonotype subset (full ImmuneBuilder runs are slow, so pick the
 *      smallest sane fixture).
 *   4. Add this block + select the upstream PDB ResourceMap via
 *      `BlockData.primaryRef.column`.
 *   5. Run, await done, assert the expected PColumns surface.
 *
 * Until that fixture exists, the block is verified end-to-end manually
 * via the desktop app + pl MCP server against real upstream data.
 */
blockTest("block loads without crashing", { timeout: 10000 }, async ({ rawPrj: project }) => {
  const blockId = await project.addBlock("3D Structure-Based Liabilities", blockSpec);
  const overview = await project.overview.getValue();
  const block = overview?.blocks.find((b) => b.id === blockId);
  if (!block) throw new Error("block not in project overview");
});
