from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Atom:
    name: str
    x: float
    y: float
    z: float
    # PDB B-factor (temperature factor). ImmuneBuilder repurposes this column
    # to carry per-atom predicted positional error in Angstroms (R29 upstream
    # guarantee). For experimental crystal structures it stays the literal
    # B-factor; the spec treats both interchangeably for R34 gating.
    b_factor: float = 0.0


@dataclass
class Residue:
    res_seq: int
    i_code: str
    res_name: str
    atoms: List[Atom] = field(default_factory=list)

    def atom(self, name: str) -> Optional[Atom]:
        for a in self.atoms:
            if a.name == name:
                return a
        return None


@dataclass
class Ssbond:
    chain1: str
    res1: int
    i_code1: str
    chain2: str
    res2: int
    i_code2: str


@dataclass
class Parsed:
    chain_order: List[str] = field(default_factory=list)
    residues_by_chain: Dict[str, List[Residue]] = field(default_factory=dict)
    ssbonds: List[Ssbond] = field(default_factory=list)


def parse_pdb(text: str) -> Parsed:
    out = Parsed()
    # Residues are keyed by (chain, res_seq, i_code); atoms accumulate per residue.
    residues: Dict[str, Residue] = {}
    in_first_model = True
    model_count = 0

    for raw in text.splitlines():
        line = raw.ljust(80)
        tag = line[0:6].rstrip()

        if tag == "MODEL":
            model_count += 1
            if model_count > 1:
                in_first_model = False
        elif tag == "SSBOND":
            try:
                chain1 = line[15:16]
                res1 = int(line[17:21].strip())
                i_code1 = line[21:22].strip()
                chain2 = line[29:30]
                res2 = int(line[31:35].strip())
                i_code2 = line[35:36].strip()
            except ValueError:
                continue
            out.ssbonds.append(
                Ssbond(
                    chain1=chain1,
                    res1=res1,
                    i_code1=i_code1,
                    chain2=chain2,
                    res2=res2,
                    i_code2=i_code2,
                )
            )
        elif tag in ("ATOM", "HETATM"):
            if not in_first_model:
                continue
            # altLoc: only keep the primary location (' ' or 'A') so geometry
            # tests don't see alternate side-chain conformers.
            alt_loc = line[16:17]
            if alt_loc not in (" ", "A"):
                continue
            atom_name = line[12:16].strip()
            res_name = line[17:20].strip()
            chain_id = line[21:22] if line[21:22] != "" else " "
            try:
                res_seq = int(line[22:26].strip())
            except ValueError:
                continue
            i_code = line[26:27].strip()
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            try:
                b_factor = float(line[60:66])
            except ValueError:
                b_factor = 0.0

            key = f"{chain_id}|{res_seq}|{i_code}"
            res = residues.get(key)
            if res is None:
                res = Residue(res_seq=res_seq, i_code=i_code, res_name=res_name)
                residues[key] = res
                if chain_id not in out.residues_by_chain:
                    out.residues_by_chain[chain_id] = []
                    out.chain_order.append(chain_id)
                out.residues_by_chain[chain_id].append(res)
            res.atoms.append(Atom(name=atom_name, x=x, y=y, z=z, b_factor=b_factor))
    return out
