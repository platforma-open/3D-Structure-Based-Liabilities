import type { ImportFileHandle, InferOutputsType } from "@platforma-sdk/model";
import { BlockModelV3, DataModelBuilder } from "@platforma-sdk/model";

export type BlockData = {
  pdb: ImportFileHandle | undefined;
};

const dataModel = new DataModelBuilder().from<BlockData>("v1").init(() => ({ pdb: undefined }));

export const platforma = BlockModelV3.create(dataModel)
  .args((data) => {
    if (!data.pdb) throw new Error("PDB file is required");
    return { pdb: data.pdb };
  })
  .output("pdbContent", (ctx) => ctx.outputs?.resolve("pdbFile")?.getFileContentAsString())
  .sections((_ctx) => [{ type: "link", href: "/", label: "Main" }])
  .done();

export type BlockOutputs = InferOutputsType<typeof platforma>;
