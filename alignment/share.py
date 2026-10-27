"""The dial board as a URL, and a run as a file.

A configuration in this app is an argument: *at these settings, the agent
lies*. An argument nobody else can reproduce is not worth much, so every dial
lives in the query string and a link replays the run exactly -- same seed, same
trace, same charts.

Only dials that differ from the defaults are written. The link therefore reads
as a diff against the default world rather than a dump of forty parameters,
which also makes it short enough to paste into a message.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from urllib.parse import urlencode, urlsplit, urlunsplit

import streamlit as st

from .model import HORIZONS, Knobs, Mitigations, RANGES, RunResult
from .scenarios import SCENARIO_ORDER

#: Every shareable field, under the same `k_`/`m_` prefixed names the preset
#: dictionaries use, mapped to the value that means "unchanged".
DEFAULTS: dict[str, object] = {
    **{f"k_{k}": v for k, v in asdict(Knobs()).items()},
    **{f"m_{k}": v for k, v in asdict(Mitigations()).items()},
}

#: Fields whose value has to come from a fixed list rather than a range.
_CHOICES: dict[str, list[str]] = {
    "k_scenario": list(SCENARIO_ORDER),
    "k_horizon": list(HORIZONS),
}

_TRUTHY = {"1", "true", "yes", "on"}


def _encode(value) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _decode(name: str, raw: str):
    """Parse one query value, or return None if it cannot be used.

    Links get hand-edited, so nothing here trusts its input: unknown choices
    are dropped and numbers are clamped into the range their own widget
    allows, since a value outside it would make that widget throw on render.
    """
    default = DEFAULTS[name]
    if name in _CHOICES:
        return raw if raw in _CHOICES[name] else None
    if isinstance(default, bool):
        return raw.strip().lower() in _TRUTHY
    try:
        num = float(raw)
    except ValueError:
        return None
    if num != num or num in (float("inf"), float("-inf")):  # NaN / infinities
        return None
    lo, hi, _ = RANGES.get(name, (num, num, 0.0))
    num = min(max(num, lo), hi)
    return int(round(num)) if isinstance(default, int) else float(num)


def to_params(knobs: dict, mits: dict) -> dict[str, str]:
    """The non-default half of a configuration, ready for a query string."""
    current = {
        **{f"k_{k}": v for k, v in knobs.items()},
        **{f"m_{k}": v for k, v in mits.items()},
    }
    out: dict[str, str] = {}
    for name, value in current.items():
        default = DEFAULTS.get(name)
        if isinstance(value, float) and isinstance(default, float):
            if abs(value - default) < 1e-9:
                continue
        elif value == default:
            continue
        out[name] = _encode(value)
    return out


def read_url(knobs: dict, mits: dict) -> int:
    """Fold a configuration in the query string into the two stores in place.

    Returns how many dials the link actually set, so the caller can tell the
    visitor they are not looking at the default world.
    """
    applied = 0
    for name, raw in st.query_params.to_dict().items():
        if name not in DEFAULTS:
            continue
        value = _decode(name, raw)
        if value is None:
            continue
        (knobs if name.startswith("k_") else mits)[name[2:]] = value
        applied += 1
    return applied


def write_url(knobs: dict, mits: dict) -> None:
    """Keep the address bar equal to the current dial board.

    Query params this module does not own -- campaign tags, anything a host
    page appended -- are carried through untouched; only the dials are
    rewritten. Writing params does not rerun the script, so this is safe on
    every pass, and the guard just avoids pointless history churn.
    """
    existing = st.query_params.to_dict()
    foreign = {k: v for k, v in existing.items() if k not in DEFAULTS}
    params = {**foreign, **to_params(knobs, mits)}
    if existing != params:
        st.query_params.from_dict(params)


def share_link(knobs: dict, mits: dict) -> str:
    """The full URL that reproduces this configuration."""
    query = urlencode(to_params(knobs, mits))
    parts = urlsplit(st.context.url or "")
    if not parts.netloc:  # no browser context -- hand back what we can
        return f"?{query}" if query else "?"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def run_manifest(run: RunResult) -> str:
    """One JSON document holding what was set and what came of it.

    The point of pairing the settings with the summary is that neither half
    means anything alone: a deception rate is only a finding if the world that
    produced it travels with it.
    """
    return json.dumps(
        {
            "scenario": run.scenario_key,
            "quota": run.quota,
            "knobs": asdict(run.knobs),
            "mitigations": asdict(run.mits),
            "summary": run.summary,
            "events": run.events,
            "query_string": urlencode(
                to_params(asdict(run.knobs), asdict(run.mits))
            ),
        },
        indent=2,
    )
