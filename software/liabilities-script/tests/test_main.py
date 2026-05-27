"""Tests for `analyze_pdb` rejection paths. The spec edge-case table calls
these out explicitly (block-structure-liabilities.md:330):

  - PDB has 3+ chains  → reject with explicit error
  - Single chain > 180 aa  → reject as suspected scFv (R7)
  - REMARK 99 absent + no --numbering-scheme → fail-fast (R10)

All three rejections fire before FreeSASA runs, so the tests can use
minimal synthetic PDBs without worrying about SASA compatibility."""

from tests.pdb_fixtures import make_chain, make_pdb

import pytest

from main import analyze_pdb


def _write(tmp_path, text: str):
    p = tmp_path / "input.pdb"
    p.write_text(text)
    return p


def _common_args(pdb_path):
    return {
        "pdb_path": pdb_path,
        "numbering_scheme": "imgt",
        "chain_h": None,
        "chain_l": None,
        "rsasa_buried_cutoff": 0.075,
        "fr_conf_thresh": 4.0,
        "cdr_conf_thresh": 6.0,
    }


class TestR7ChainCount:
    """Spec R7: chain count determines mode. 0 chains, 3+ chains, and
    suspected scFv (single chain > 180 aa) are explicit rejections."""

    def test_zero_chains_rejected(self, tmp_path):
        path = _write(tmp_path, "")
        with pytest.raises(ValueError, match="no ATOM records"):
            analyze_pdb(**_common_args(path))

    def test_three_chains_rejected(self, tmp_path):
        text = make_pdb([
            ("A", 1, "ALA", 20.0),
            ("B", 1, "GLY", 20.0),
            ("C", 1, "VAL", 20.0),
        ])
        path = _write(tmp_path, text)
        with pytest.raises(ValueError, match="3 chains"):
            analyze_pdb(**_common_args(path))

    def test_four_chains_rejected(self, tmp_path):
        text = make_pdb([
            ("A", 1, "ALA", 20.0),
            ("B", 1, "GLY", 20.0),
            ("C", 1, "VAL", 20.0),
            ("D", 1, "LEU", 20.0),
        ])
        path = _write(tmp_path, text)
        with pytest.raises(ValueError, match="4 chains"):
            analyze_pdb(**_common_args(path))

    def test_single_chain_over_180aa_rejected_as_scfv(self, tmp_path):
        """181 residues in one chain trips the scFv heuristic. The threshold
        is hardcoded to 180 in main.analyze_pdb."""
        text = make_pdb(make_chain("H", 200))
        path = _write(tmp_path, text)
        with pytest.raises(ValueError, match="scFv"):
            analyze_pdb(**_common_args(path))


class TestR10NumberingSource:
    """Spec R10: numbering source must be available. With neither REMARK 99
    records nor a `--numbering-scheme` value, the run fails fast (before
    FreeSASA so the rejection is cheap)."""

    def test_no_remark_no_scheme_rejected(self, tmp_path):
        # Two-chain PDB so the R7 check passes; no REMARK 99 lines.
        text = make_pdb([("A", 1, "ALA", 20.0), ("B", 1, "GLY", 20.0)])
        path = _write(tmp_path, text)
        args = _common_args(path)
        args["numbering_scheme"] = None
        with pytest.raises(ValueError, match="spec R10"):
            analyze_pdb(**args)
