"""Stage 4 PyMC prior centers — pulled from make_nominal_params.

Per CONTEXT.md §Claude's Discretion: log-normal priors on strictly-positive rates.
Pitfall 3 mitigation: T_act uses informative LogNormal(log(25), 0.3) — prevents
β_therm↔T_act degeneracy.

Per D-08: no hierarchical model across compounds in v1 — all compounds share the
same nominal prior centers from make_nominal_params(). Compound-specific nominal
differences can enter v2.
"""
from __future__ import annotations
from f1_core.physics.defaults import make_nominal_params


def degradation_prior_centers(compound: str) -> dict[str, float]:
    """Return prior center values for Stage 4 degradation MCMC.

    v1: per-compound calibration uses the same nominal centers for all compounds
    (D-08, no hierarchical model). Compound-specific nominal differences can enter v2.

    Args:
        compound: Pirelli compound code, e.g. 'C3'. Used for v2 compound-specific
                  prior adjustments; ignored in v1.

    Returns:
        Dict with keys: 'beta_therm', 'T_act', 'k_wear' — center values for
        LogNormal priors in Stage 4 PyMC model.

    Example::
        centers = degradation_prior_centers("C3")
        # {"beta_therm": 1e-6, "T_act": 25.0, "k_wear": 1e-12}
    """
    nominal = make_nominal_params().degradation
    return {
        "beta_therm": nominal.beta_therm,  # 1e-6 /s — thermal aging rate
        "T_act": nominal.T_act,            # 25.0 °C — Arrhenius activation temperature
        "k_wear": nominal.k_wear,          # 1e-12 m/(W·s) — mechanical wear coefficient
    }


__all__ = ["degradation_prior_centers"]
