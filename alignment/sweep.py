"""Parameter sweeps and intervention comparisons.

Single runs are anecdotes. These functions average over seeds so the claims the
app makes ("pressure drives misconduct", "hard constraints beat big weights")
rest on distributions rather than on one lucky trace.
"""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd
import streamlit as st

from .engine import simulate
from .model import Knobs, Mitigations


def _mean(knobs: Knobs, mits: Mitigations, seeds: int) -> dict[str, float]:
    out: dict[str, list[float]] = {}
    for s in range(seeds):
        summary = simulate(knobs.copy(seed=knobs.seed + s), mits).summary
        for k, v in summary.items():
            out.setdefault(k, []).append(v)
    return {k: float(np.mean(v)) for k, v in out.items()}


@st.cache_data(show_spinner=False, max_entries=48, ttl=3600)
def run_cached(knobs_d: dict, mits_d: dict):
    return simulate(Knobs(**knobs_d), Mitigations(**mits_d))


def run(knobs: Knobs, mits: Mitigations):
    return run_cached(asdict(knobs), asdict(mits))


@st.cache_data(show_spinner="Sweeping the parameter space...", max_entries=12, ttl=3600)
def phase_map(
    knobs_d: dict,
    mits_d: dict,
    pressures: tuple[float, ...],
    oversights: tuple[float, ...],
    seeds: int = 3,
) -> pd.DataFrame:
    """Deception rate across the pressure x oversight plane."""
    base, mits = Knobs(**knobs_d), Mitigations(**mits_d)
    rows = []
    for p in pressures:
        for o in oversights:
            m = _mean(base.copy(target_pressure=p, oversight_coverage=o), mits, seeds)
            rows.append(
                {
                    "pressure": p,
                    "oversight": o,
                    "deception_rate": m["deception_rate"],
                    "deviance_rate": m["deviance_rate"],
                    "true_value": m["true_value"],
                    "goodhart_gap": m["goodhart_gap"],
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Comparing interventions...", max_entries=12, ttl=3600)
def compare_bundles(
    knobs_d: dict, bundles: tuple[tuple[str, dict], ...], seeds: int = 5
) -> pd.DataFrame:
    base = Knobs(**knobs_d)
    rows = []
    for label, mdict in bundles:
        m = _mean(base, Mitigations(**mdict), seeds)
        rows.append(
            {
                "label": label,
                "deception_rate": m["deception_rate"],
                "deviance_rate": m["deviance_rate"],
                "true_value": m["true_value"],
                "reported": m["reported"],
                "goodhart_gap": m["goodhart_gap"],
                "caught": m["caught"],
                "quota": m["quota"],
            }
        )
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, max_entries=12, ttl=3600)
def pressure_curve(
    knobs_d: dict, mits_variants: tuple[tuple[str, dict], ...],
    pressures: tuple[float, ...], seeds: int = 3,
) -> pd.DataFrame:
    base = Knobs(**knobs_d)
    rows = []
    for label, mdict in mits_variants:
        mits = Mitigations(**mdict)
        for p in pressures:
            m = _mean(base.copy(target_pressure=p), mits, seeds)
            rows.append(
                {
                    "label": label,
                    "pressure": p,
                    "deception_rate": m["deception_rate"],
                    "deviance_rate": m["deviance_rate"],
                    "true_value": m["true_value"],
                }
            )
    return pd.DataFrame(rows)
