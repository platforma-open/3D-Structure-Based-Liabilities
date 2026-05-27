# Regex set + weights + risk taxonomy copied VERBATIM from
# blocks/antibody-sequence-liabilities/liabilities-calc-script/src/definitions.py
# (R16). Spec requires this block to be standalone , no import , to avoid
# silent half-coupling. A parity check vs the source is owed at M1.

import math
import re
from dataclasses import dataclass
from typing import Optional

from structure import region_for, role_of_chain

# name -> (regex pattern, risk_level, fixability)
ORIG_REGEX_LIABILITIES = {
    "Deamidation (N[GS])": (r"N[GS]", "High", "fixable"),
    "Fragmentation (DP)": (r"DP", "High", "fixable"),
    "Isomerization (D[DGHST])": (r"D[DGHST]", "High", "fixable"),
    "N-linked Glycosylation (N[^P][ST])": (r"N[^P][ST]", "High", "fixable"),
    "Deamidation (N[AHNT])": (r"N[AHNT]", "Medium", "easily_fixable"),
    "Hydrolysis (NP)": (r"NP", "Medium", "fixable"),
    "Fragmentation (TS)": (r"TS", "Medium", "fixable"),
    "Tryptophan Oxidation (W)": (r"W", "Medium", "easily_fixable"),
    "Methionine Oxidation (M)": (r"M", "Medium", "easily_fixable"),
    "Deamidation ([STK]N)": (r"[STK]N", "Low", "easily_fixable"),
    "Integrin binding": (r"RGD|RYD|KGD|NGR|LDV|DGE|GPR", "Low", "easily_fixable"),
}

FIXABILITY_WEIGHTS = {
    "easily_fixable": 1.0,
    "fixable": 3.0,
    "hard_to_fix": 8.0,
    "structural": 20.0,
    "disqualifying": 0.0,
}

# R19 region weights. Until per-residue region tagging is wired (needs
# numbering from REMARK 99 / R10), region resolves to None and the neutral
# default is applied so scores stay comparable across calls.
REGION_WEIGHTS = {
    "CDR3": 1.5,
    "CDR1": 1.2,
    "CDR2": 1.2,
    "FR1": 1.0,
    "FR2": 0.5,
    "FR3": 0.5,
    "FR4": 0.3,
}
REGION_WEIGHT_DEFAULT = 1.0

# R17: index within each regex match of the chemically-relevant residue whose
# rSASA gates the call. N in N[GS] deamidation, D in D[DGHST] isomerization,
# W in tryptophan oxidation -> position 0. [STK]N puts the relevant Asn at
# position 1. Multi-residue motifs (integrin, fragmentation) use position 0;
# any contributing residue's accessibility is informative for the whole motif.
CHEMICALLY_RELEVANT_INDEX = {
    "Deamidation (N[GS])": 0,
    "Fragmentation (DP)": 0,
    "Isomerization (D[DGHST])": 0,
    "N-linked Glycosylation (N[^P][ST])": 0,
    "Deamidation (N[AHNT])": 0,
    "Hydrolysis (NP)": 0,
    "Fragmentation (TS)": 0,
    "Tryptophan Oxidation (W)": 0,
    "Methionine Oxidation (M)": 0,
    "Deamidation ([STK]N)": 1,
    "Integrin binding": 0,
}

AA_THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


@dataclass
class MotifHit:
    type: str
    chainId: str
    resSeq: int
    iCode: str
    resName: str
    region: str | None
    # R18: absolute SASA (Å²) for the chemically-relevant residue, paired
    # with rSASA. Spec mandates both even though rSASA × Ala-X-Ala ref
    # recovers it , keeping the raw value makes downstream analytics
    # comparable to TAP-style reports without a back-conversion step.
    sasa: float | None
    rsasa: float
    exposed: bool
    exposureFactor: float
    # R34: residue's local positional uncertainty in Angstroms. For
    # ImmuneBuilder PDBs this is per-atom predicted error stored in the
    # B-factor column; for crystal structures it's the literal B-factor.
    # We average atom B-factors per residue (mean across all heavy atoms).
    confidence: Optional[float]
    # R35: True when confidence exceeds the region-aware threshold.
    # confidenceGated motifs are kept in the table but excluded from
    # motifStructuralRiskScore. String "yes"/"no" so it round-trips through
    # the PColumn String value type cleanly (bool isn't a PColumn type).
    confidenceGated: str
    weightedScore: float
    sequenceRiskClass: str
    fixability: str


def _exposure_factor(rsasa: float | None) -> float:
    # R20: logistic centered at 0.30 , avoids a cliff at the buried/exposed
    # cutoff so transitional residues taper smoothly into the score.
    if rsasa is None:
        return 0.0
    return 1.0 / (1.0 + math.exp(-20.0 * (rsasa - 0.30)))


def _chain_letters(residues):
    # Map each residue to a single-letter code; non-canonical residues
    # (HETATM, modified residues like MSE) collapse to "X" so motif matches
    # never span them.
    letters = []
    for r in residues:
        letters.append(AA_THREE_TO_ONE.get(r.res_name, "X"))
    return "".join(letters)


def _mean_b_factor(
    residue,
    fallback_lookup: Optional[dict] = None,
    chain_id: Optional[str] = None,
) -> Optional[float]:
    # Mean B-factor across heavy atoms of the residue. None when no atoms
    # carry positive B-factor (e.g. coords parsed without it). R4: when the
    # B-factor is missing AND an upstream per-residue confidence lookup is
    # supplied, fall back to its errorAngstroms value for this residue.
    if residue.atoms:
        vals = [a.b_factor for a in residue.atoms if a.b_factor > 0]
        if vals:
            return sum(vals) / len(vals)
    if fallback_lookup is not None and chain_id is not None:
        pos_key = f"{residue.res_seq}{residue.i_code}".strip()
        return fallback_lookup.get((chain_id, pos_key))
    return None


def _confidence_threshold(region: Optional[str], fr_threshold: float, cdr_threshold: float) -> float:
    # R34: region-aware thresholds. CDRs get the looser cutoff because
    # ImmuneBuilder's predicted error is structurally larger there. When
    # region is unknown ("-" / None) fall back to FR threshold (the stricter
    # one) so untagged regions don't slip ambiguous calls through.
    if region in ("CDR1", "CDR2", "CDR3"):
        return cdr_threshold
    return fr_threshold


def _score_motif_hit(
    *,
    motif_name: str,
    chain_id: str,
    residue,
    region: Optional[str],
    sasa: Optional[float],
    rsasa: float,
    risk: str,
    fixability: str,
    fixability_weight: float,
    fr_confidence_threshold: float,
    cdr_confidence_threshold: float,
    confidence_fallback: Optional[dict] = None,
) -> MotifHit:
    """Assemble a single MotifHit once we know the residue passes R17
    surface exposure. Pulled out so the main loop reads as
    "find matches → score each match" rather than 15 lines of inline
    arithmetic per hit.

    Computes:
      • exposureFactor  , R20 logistic on rSASA (smooths the buried/exposed
                          cliff at 0.30).
      • confidence       , residue's mean heavy-atom B-factor (R34).
      • confidenceGated  , true when B-factor exceeds the region-aware
                          threshold (R35); gated hits stay in the table
                          for traceability but skip motifStructuralRiskScore.
      • weightedScore    , fixability_weight × region_weight × exposureFactor.
                          The R19 region weight rewards CDR-localized hits
                          (most therapeutically relevant) over framework.
    """
    region_weight = REGION_WEIGHTS.get(region, REGION_WEIGHT_DEFAULT)
    exposure_factor = _exposure_factor(rsasa)
    confidence = _mean_b_factor(residue, confidence_fallback, chain_id)
    threshold = _confidence_threshold(region, fr_confidence_threshold, cdr_confidence_threshold)
    gated = confidence is not None and confidence > threshold
    return MotifHit(
        type=motif_name,
        chainId=chain_id,
        resSeq=residue.res_seq,
        iCode=residue.i_code,
        resName=residue.res_name,
        region=region,
        sasa=sasa,
        rsasa=rsasa,
        exposed=True,
        exposureFactor=exposure_factor,
        confidence=confidence,
        confidenceGated="yes" if gated else "no",
        weightedScore=fixability_weight * region_weight * exposure_factor,
        sequenceRiskClass=risk,
        fixability=fixability,
    )


def detect_motifs(
    parsed,
    sasa_lookup,
    rsasa_buried_cutoff: float = 0.075,
    numbering_scheme: Optional[str] = None,
    heavy_chain_id: Optional[str] = None,
    light_chain_id: Optional[str] = None,
    fr_confidence_threshold: float = 4.0,
    cdr_confidence_threshold: float = 6.0,
    confidence_fallback: Optional[dict] = None,
):
    """Walk each chain, apply the regex set, and emit hits whose
    chemically-relevant residue (R17) has rSASA >= cutoff. Buried matches
    are suppressed entirely per the spec, not just down-weighted , a buried
    NG can't be deamidated, so flagging it would be a false positive.

    When numbering_scheme + heavy/light chain mapping are supplied, hits get
    a real `region` (FR1/CDR1/.../FR4) and the R19 region weight is applied
    to weightedScore. Otherwise `region` stays None and the neutral default
    is used.
    """
    hits: list[MotifHit] = []
    compiled = {name: re.compile(pat) for name, (pat, _r, _f) in ORIG_REGEX_LIABILITIES.items()}

    for chain_id in parsed.chain_order:
        residues = parsed.residues_by_chain[chain_id]
        seq = _chain_letters(residues)
        chain_role = role_of_chain(chain_id, heavy_chain_id, light_chain_id)

        for motif_name, regex in compiled.items():
            _pat, risk, fixability = ORIG_REGEX_LIABILITIES[motif_name]
            # R17: the "chemically-relevant" residue is the position within
            # the motif that actually undergoes the modification (e.g. the
            # N in an N-G deamidation pair). Index is per-motif because some
            # patterns are multi-character but the at-risk site isn't always
            # at offset 0.
            relevant_offset = CHEMICALLY_RELEVANT_INDEX[motif_name]
            fixability_weight = FIXABILITY_WEIGHTS.get(fixability, 0.0)

            for match in regex.finditer(seq):
                pos_in_seq = match.start() + relevant_offset
                if pos_in_seq >= len(residues):
                    continue
                residue = residues[pos_in_seq]
                if AA_THREE_TO_ONE.get(residue.res_name) is None:
                    # Non-standard residue , skip (we can't trust the
                    # 1-letter translation that fed the regex match).
                    continue
                key = (chain_id, f"{residue.res_seq}{residue.i_code}".strip())
                sasa_info = sasa_lookup.get(key, {})
                rsasa = sasa_info.get("rsasa")
                if rsasa is None or rsasa < rsasa_buried_cutoff:
                    continue
                region = region_for(
                    chain_role, residue.res_seq, numbering_scheme, parsed.platforma_cdrs
                )
                hits.append(_score_motif_hit(
                    motif_name=motif_name,
                    chain_id=chain_id,
                    residue=residue,
                    region=region,
                    sasa=sasa_info.get("sasa"),
                    rsasa=rsasa,
                    risk=risk,
                    fixability=fixability,
                    fixability_weight=fixability_weight,
                    fr_confidence_threshold=fr_confidence_threshold,
                    cdr_confidence_threshold=cdr_confidence_threshold,
                    confidence_fallback=confidence_fallback,
                ))
    return hits
