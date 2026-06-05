"""Tests for `motifs._mean_b_factor`: covers the B-factor JSON
fallback and the basic positive-B-factor path used by the confidence
gating."""

from structure import Atom, Residue

from motifs import _mean_b_factor


def _residue(b_factors: list[float], res_seq: int = 100, i_code: str = "") -> Residue:
    return Residue(
        res_seq=res_seq,
        i_code=i_code,
        res_name="ASN",
        atoms=[Atom(name=f"X{i}", x=0.0, y=0.0, z=0.0, b_factor=b) for i, b in enumerate(b_factors)],
    )


class TestMeanBFactor:
    """B-factor stays as the primary confidence signal; the fallback
    only fires when every atoms B-factor is zero (this is the
    fallback path "fallback only")."""

    def test_uniform_b_factors(self):
        assert _mean_b_factor(_residue([2.0, 4.0, 6.0])) == 4.0

    def test_zero_b_factors_yields_none_without_fallback(self):
        """ImmuneBuilder always emits non-zero B-factors; a fully-zero
        residue means we have no in-PDB confidence signal."""
        assert _mean_b_factor(_residue([0.0, 0.0])) is None

    def test_partial_zero_b_factors_average_only_nonzero(self):
        """Mixed atoms: keep the heavy atoms with positive B-factor only.
        Defends against PDBs where one atom got dropped from the prediction
        but the rest are valid."""
        assert _mean_b_factor(_residue([0.0, 4.0, 6.0])) == 5.0

    def test_no_atoms_yields_none(self):
        empty = Residue(res_seq=100, i_code="", res_name="ASN", atoms=[])
        assert _mean_b_factor(empty) is None


class TestR4BFactorFallback:
    """When the PDB B-factor column is empty AND the upstream
    per-residue JSON column is supplied, fall back to its errorAngstroms
    value. ImmuneBuilder always populates B-factors, so this path is the
    "edge case" for crystal PDBs or pipelines that do not carry per-atom error."""

    def test_fallback_used_when_b_factors_all_zero(self):
        fallback = {("H", "100"): 3.5}
        result = _mean_b_factor(_residue([0.0, 0.0]), fallback, "H")
        assert result == 3.5

    def test_fallback_skipped_when_b_factors_present(self):
        """In-PDB B-factor wins , don't second-guess a positive signal."""
        fallback = {("H", "100"): 99.0}
        result = _mean_b_factor(_residue([4.0, 6.0]), fallback, "H")
        assert result == 5.0

    def test_fallback_with_icode(self):
        """Insertion code is part of the lookup key (e.g. H100A)."""
        fallback = {("H", "100A"): 2.8}
        residue = _residue([0.0], res_seq=100, i_code="A")
        assert _mean_b_factor(residue, fallback, "H") == 2.8

    def test_fallback_miss_yields_none(self):
        """No entry in the fallback for this (chain, pos) , same outcome
        as no fallback at all."""
        fallback = {("H", "200"): 3.5}
        result = _mean_b_factor(_residue([0.0]), fallback, "H")
        assert result is None

    def test_no_chain_id_skips_fallback(self):
        """Without chain context, the lookup can't be performed; return None
        rather than picking the first match."""
        fallback = {("H", "100"): 3.5}
        result = _mean_b_factor(_residue([0.0]), fallback, None)
        assert result is None
