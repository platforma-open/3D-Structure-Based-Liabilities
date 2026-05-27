"""Tests for `structure.py` — parse_pdb, region_for, role_of_chain, and
the R10 / R9 numbering plumbing they feed."""

from tests.pdb_fixtures import make_chain, make_pdb

from structure import SCHEME_CDR_RANGES, parse_pdb, region_for, role_of_chain


class TestParsePdb:
    """Spec R7 chain dispatch hinges on `parse_pdb` reporting the right
    chain_order. These tests don't need FreeSASA — `parse_pdb` is pure
    string parsing."""

    def test_empty_input_yields_zero_chains(self):
        parsed = parse_pdb("")
        assert parsed.chain_order == []
        assert parsed.residues_by_chain == {}

    def test_single_chain_record(self):
        parsed = parse_pdb(make_pdb([("H", 1, "ALA", 20.0)]))
        assert parsed.chain_order == ["H"]
        assert len(parsed.residues_by_chain["H"]) == 1

    def test_two_chains_register_in_order(self):
        parsed = parse_pdb(make_pdb([("H", 1, "ALA", 20.0), ("L", 1, "GLY", 20.0)]))
        assert parsed.chain_order == ["H", "L"]

    def test_three_chains_register_all(self):
        """R7 inline check in main.analyze_pdb rejects on len(chain_order) >= 3.
        The parser itself records all of them; the rejection is downstream."""
        parsed = parse_pdb(make_pdb([
            ("A", 1, "ALA", 20.0),
            ("B", 1, "GLY", 20.0),
            ("C", 1, "VAL", 20.0),
        ]))
        assert len(parsed.chain_order) == 3

    def test_non_canonical_chain_ids_preserved(self):
        """R9: chain IDs `A`/`B` (rather than `H`/`L`) are accepted as-is.
        Mapping to roles happens via REMARK 99 or --chain-h/--chain-l args."""
        parsed = parse_pdb(make_pdb([("A", 1, "ALA", 20.0), ("B", 1, "GLY", 20.0)]))
        assert parsed.chain_order == ["A", "B"]

    def test_remark_99_platforma_cdr_record_parsed(self):
        """R10 preferred path: REMARK 99 PLATFORMA CDR records populate
        `platforma_cdrs` and `chain_role_to_pdb_chain`. Spec wire format
        is `CDR<H|L><1|2|3> <chain><start>-<chain><end>`."""
        text = (
            "REMARK  99 PLATFORMA CDRH1 B26-B32                                              \n"
            "REMARK  99 PLATFORMA CDRL1 A24-A34                                              \n"
            + make_pdb([("B", 1, "ALA", 20.0), ("A", 1, "GLY", 20.0)])
        )
        parsed = parse_pdb(text)
        assert parsed.platforma_cdrs["H"]["CDR1"] == (26, 32)
        assert parsed.platforma_cdrs["L"]["CDR1"] == (24, 34)
        # R9: REMARK 99 chain field is authoritative — `B` is the heavy chain
        # even though it's not the canonical letter.
        assert parsed.chain_role_to_pdb_chain["H"] == "B"
        assert parsed.chain_role_to_pdb_chain["L"] == "A"

    def test_b_factor_parsed_per_atom(self):
        parsed = parse_pdb(make_pdb([("H", 1, "ALA", 12.5)]))
        atom = parsed.residues_by_chain["H"][0].atoms[0]
        assert atom.b_factor == 12.5

    def test_multi_model_keeps_only_first(self):
        text = (
            "MODEL        1                                                                  \n"
            + make_pdb([("H", 1, "ALA", 20.0)])
            + "ENDMDL                                                                          \n"
            + "MODEL        2                                                                  \n"
            + make_pdb([("H", 1, "GLY", 30.0)])
            + "ENDMDL                                                                          \n"
        )
        parsed = parse_pdb(text)
        assert len(parsed.residues_by_chain["H"]) == 1
        # First-model atom kept, second-model atom dropped
        assert parsed.residues_by_chain["H"][0].res_name == "ALA"

    def test_long_single_chain_supported(self):
        """200 residues in one chain — parse_pdb just records them. The R7
        scFv rejection (>180 single-chain) is a downstream check in
        main.analyze_pdb."""
        parsed = parse_pdb(make_pdb(make_chain("H", 200)))
        assert len(parsed.residues_by_chain["H"]) == 200


class TestRegionFor:
    """R10 fallback: scheme-aware fixed ranges when REMARK 99 records are
    absent. Pure-function lookup, no PDB parsing required."""

    def test_imgt_cdr1_range(self):
        cdr1_lo, cdr1_hi = SCHEME_CDR_RANGES["imgt"]["H"]["CDR1"]
        assert region_for("H", cdr1_lo, "imgt", {}) == "CDR1"
        assert region_for("H", cdr1_hi, "imgt", {}) == "CDR1"
        assert region_for("H", cdr1_hi + 1, "imgt", {}) == "FR2"

    def test_chothia_cdr3_range(self):
        cdr3_lo, cdr3_hi = SCHEME_CDR_RANGES["chothia"]["H"]["CDR3"]
        assert region_for("H", cdr3_lo, "chothia", {}) == "CDR3"
        assert region_for("H", cdr3_hi, "chothia", {}) == "CDR3"

    def test_unknown_chain_role_returns_none(self):
        """Antigen chains in a complex have no chain role; region tagging
        falls through to None (motif scoring then uses REGION_WEIGHT_DEFAULT)."""
        assert region_for(None, 50, "imgt", {}) is None

    def test_remark_99_overrides_scheme_fallback(self):
        """When REMARK 99 CDR ranges are present for ALL three CDRs, they
        override the scheme-fixed ranges (R10 preferred path). Partial
        overrides (one or two CDRs) are ignored — see the next test."""
        platforma_cdrs = {"H": {"CDR1": (40, 50), "CDR2": (60, 70), "CDR3": (100, 115)}}
        # 40 lands in REMARK CDR1, NOT IMGT CDR1 (which starts at 27).
        assert region_for("H", 40, "imgt", platforma_cdrs) == "CDR1"
        assert region_for("H", 27, "imgt", platforma_cdrs) == "FR1"

    def test_partial_remark_99_falls_back_to_scheme(self):
        """If only CDR1 is present in REMARK 99, the override is rejected
        and scheme-fixed ranges drive every CDR (consistency check)."""
        partial = {"H": {"CDR1": (40, 50)}}
        # IMGT CDR1 starts at 27, so 40 lands in FR2 here.
        assert region_for("H", 40, "imgt", partial) == "FR2"


class TestRoleOfChain:
    """R9: physical PDB chain IDs (sometimes `A`/`B` rather than `H`/`L`)
    map to the canonical heavy/light role via REMARK 99 records or the
    `--chain-h`/`--chain-l` CLI overrides."""

    def test_heavy_match(self):
        assert role_of_chain("B", "B", "A") == "H"

    def test_light_match(self):
        assert role_of_chain("A", "B", "A") == "L"

    def test_canonical_letters_also_work(self):
        assert role_of_chain("H", "H", "L") == "H"
        assert role_of_chain("L", "H", "L") == "L"

    def test_unmapped_chain_returns_none(self):
        """Antigen chains in a complex or unmapped chain IDs return None
        so motif scoring downstream applies neutral region weights."""
        assert role_of_chain("C", "H", "L") is None

    def test_empty_mapping_returns_none(self):
        """Without a heavy/light mapping, every chain is unrole-able."""
        assert role_of_chain("H", None, None) is None
        assert role_of_chain("L", "", "") is None
