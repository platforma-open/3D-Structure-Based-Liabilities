"""Minimal PDB v3.30 parser. We only consume the records we need:

  ATOM / HETATM   — per-atom coordinates and B-factor (R34 confidence).
  SSBOND          — disulfide bonds declared in the header (R21 cross-check).
  REMARK 99       — `REMARK 99 PLATFORMA CDR<role><idx> <chain><start>-<chain><end>`
                    records emitted by the Structure Prediction block:
                      • CDR boundaries override scheme-fixed ranges (R10).
                      • The chain letter prefix is authoritative for which
                        physical chain plays the H / L role (R9).

PDB v3.30 is a fixed-column text format — every record's fields live at
specific byte offsets, not whitespace-separated tokens. Examples used here:

  ATOM   1234  CA  ARG A  42      11.234  22.345  33.456  1.00  4.50
  cols   0-5  6-10 12-15 17-19 21  22-25 26  30-37 38-45 46-53 60-65
                            ^-resName  ^-iCode  ^----- x,y,z ------^   ^B-factor
  chain at col 21, resSeq cols 22-25, altLoc at col 16, atom name 12-15.

PDB spec: https://www.wwpdb.org/documentation/file-format-content/format33/sect9.html#ATOM
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
    # Spec R10 — CDR ranges from `REMARK 99 PLATFORMA CDR*` records emitted
    # by the Structure Prediction block. Shape: {"H": {"CDR1": (start, end),
    # "CDR2": (...), "CDR3": (...)}, "L": {...}}. Empty when not present;
    # downstream code falls back to scheme-aware fixed ranges.
    platforma_cdrs: Dict[str, Dict[str, Tuple[int, int]]] = field(default_factory=dict)
    # Spec R9 — REMARK 99 chain identity is authoritative. Maps role ("H"/"L")
    # to the physical PDB chain letter the records reference. e.g. given
    # `REMARK 99 PLATFORMA CDRH1 B27-B38`, this becomes {"H": "B"}. Caller
    # uses this to override the user's heavy/light chain dropdowns when
    # records are present.
    chain_role_to_pdb_chain: Dict[str, str] = field(default_factory=dict)


# `REMARK 99 PLATFORMA CDRH1 H27-H38` per spec R10 / upstream R26. Capture
# both the role letter (group 1) and the chain letter at each end of the
# range (groups 3, 5) so we can also extract spec R9's chain identity.
_PLATFORMA_CDR_RE = re.compile(
    r"^REMARK\s+99\s+PLATFORMA\s+CDR([HL])([123])\s+([A-Za-z])(\d+)-([A-Za-z])(\d+)\s*$"
)


def parse_pdb(text: str) -> Parsed:
    out = Parsed()
    # Residues are keyed by (chain, res_seq, i_code); atoms accumulate per residue.
    residues: Dict[str, Residue] = {}
    in_first_model = True
    model_count = 0

    for raw in text.splitlines():
        # PDB lines are nominally 80 columns; many producers strip trailing
        # whitespace. Pad to a full 80 so fixed-offset slicing further down
        # never reads past the end of `raw`.
        line = raw.ljust(80)
        tag = line[0:6].rstrip()

        if tag == "MODEL":
            model_count += 1
            if model_count > 1:
                in_first_model = False
        elif tag == "REMARK":
            m = _PLATFORMA_CDR_RE.match(raw.rstrip())
            if m:
                role = m.group(1)
                cdr_idx = m.group(2)
                chain_start, start_s = m.group(3), m.group(4)
                chain_end, end_s = m.group(5), m.group(6)
                # Both ends of the range must reference the same chain.
                if chain_start.upper() != chain_end.upper():
                    continue
                try:
                    start, end = int(start_s), int(end_s)
                except ValueError:
                    continue
                if end < start:
                    continue
                out.platforma_cdrs.setdefault(role, {})[f"CDR{cdr_idx}"] = (start, end)
                # Spec R9 — record the physical PDB chain letter for this role.
                # Later records for the same role must agree; conflicts are
                # silently dropped (downstream falls back to the user's mapping).
                existing = out.chain_role_to_pdb_chain.get(role)
                if existing is None:
                    out.chain_role_to_pdb_chain[role] = chain_start
                elif existing.upper() != chain_start.upper():
                    out.chain_role_to_pdb_chain.pop(role, None)
        elif tag == "SSBOND":
            # SSBOND record fixed offsets (PDB v3.30):
            #   col 15 = chainID1, 17-20 = resSeq1, 21 = iCode1
            #   col 29 = chainID2, 31-34 = resSeq2, 35 = iCode2
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
            # ATOM / HETATM record fixed offsets (PDB v3.30). We pull:
            #   12-15 atom name        16    altLoc
            #   17-19 residue 3-letter 21    chainID
            #   22-25 residue seq num  26    iCode (insertion code)
            #   30-37 x   38-45 y      46-53 z  (Å, free-form floats)
            #   60-65 B-factor (Å² for crystals, Å for ImmuneBuilder-predicted)
            #
            # altLoc filter — multi-conformer side chains list each alternate
            # location with a letter ('A', 'B', ...). Keeping only ' ' and 'A'
            # ensures geometry tests (distance pairs, salt bridges) don't
            # double-count atoms.
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
