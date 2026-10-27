"""Shared UI: session state, control panels, presets, and KPI tiles."""

from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from . import share
from .engine import unit_scale
from .model import HORIZONS, RANGES, Knobs, Mitigations, RunResult
from .scenarios import SCENARIO_ORDER, SCENARIOS, get_scenario

_K = asdict(Knobs())
_M = asdict(Mitigations())

# Canonical values live in two plain dicts, NOT in widget keys. Streamlit
# garbage-collects widget state for widgets that a given page does not render,
# so a sidebar control that only exists on one page would silently reset to its
# minimum the moment you navigated away. Widgets read from these dicts and write
# back through on_change.
KNOB_STORE = "cfg_knobs"
MIT_STORE = "cfg_mits"


#: How many dials the link that opened this session set. Zero means the
#: visitor is looking at the default world.
FROM_LINK = "cfg_from_link"


def init_state() -> None:
    """Prepare the stores, then keep the address bar equal to them.

    The URL is read exactly once -- on the first page of a session -- because
    after that the stores are authoritative and the traffic runs the other
    way: every dial the visitor moves is written back out to the query string.
    """
    if KNOB_STORE not in st.session_state:
        st.session_state[KNOB_STORE] = dict(_K)
        st.session_state[MIT_STORE] = dict(_M)
        st.session_state[FROM_LINK] = share.read_url(
            st.session_state[KNOB_STORE], st.session_state[MIT_STORE]
        )
    share.write_url(st.session_state[KNOB_STORE], st.session_state[MIT_STORE])


def knobs() -> Knobs:
    return Knobs(**st.session_state[KNOB_STORE])


def mitigations() -> Mitigations:
    return Mitigations(**st.session_state[MIT_STORE])


def _store_for(prefixed: str) -> tuple[str, str]:
    return (KNOB_STORE if prefixed.startswith("k_") else MIT_STORE), prefixed[2:]


def apply_preset(values: dict) -> None:
    for prefixed, v in values.items():
        store, field = _store_for(prefixed)
        st.session_state[store][field] = v
        wkey = f"w_{store}_{field}"
        if wkey in st.session_state:
            st.session_state[wkey] = v


def _sync(store: str, field: str, wkey: str) -> None:
    st.session_state[store][field] = st.session_state[wkey]


def _bind(method, c, label: str, prefixed: str, value_arg: str = "value", **kw):
    """Render a widget bound to the canonical store rather than to its own key."""
    store, field = _store_for(prefixed)
    wkey = f"w_{store}_{field}"
    # Passing both a default *and* a session-state value makes Streamlit warn.
    # apply_preset keeps the widget key in step, so the default is only needed
    # the first time the widget appears.
    if wkey not in st.session_state:
        kw[value_arg] = st.session_state[store][field]
    return getattr(c, method)(
        label, key=wkey, on_change=_sync, args=(store, field, wkey), **kw
    )


def slider(c, label, prefixed, **kw):
    lo, hi, step = RANGES[prefixed]
    return _bind("slider", c, label, prefixed, min_value=lo, max_value=hi,
                 step=step, **kw)


def toggle(c, label, prefixed, **kw):
    return _bind("toggle", c, label, prefixed, **kw)


def number(c, label, prefixed, **kw):
    lo, hi, step = RANGES[prefixed]
    return _bind("number_input", c, label, prefixed, min_value=lo, max_value=hi,
                 step=step, **kw)


def select(c, label, prefixed, options, **kw):
    store, field = _store_for(prefixed)
    wkey = f"w_{store}_{field}"
    opts = list(options)
    if wkey not in st.session_state:
        kw["index"] = opts.index(st.session_state[store][field])
    return c.selectbox(
        label, opts, key=wkey, on_change=_sync, args=(store, field, wkey), **kw
    )


# --- presets ---------------------------------------------------------------

PRESSURE_PRESETS: dict[str, dict] = {
    "Reasonable target": {
        "k_target_pressure": 0.75, "k_headwind": 0.0, "k_oversight_coverage": 0.45,
        "k_channel_independence": 0.6, "k_collusion_allowed": False, "k_norm_erosion": 0.2,
    },
    "The squeeze": {
        "k_target_pressure": 1.25, "k_headwind": 0.45, "k_oversight_coverage": 0.40,
        "k_channel_independence": 0.25, "k_collusion_allowed": True, "k_norm_erosion": 0.45,
    },
    "Predictable audits": {
        "k_target_pressure": 1.20, "k_headwind": 0.40, "k_oversight_coverage": 0.30,
        "k_audit_predictable": True, "k_horizon": "far-sighted",
    },
    "Marks its own homework": {
        "k_target_pressure": 1.20, "k_headwind": 0.40, "k_channel_independence": 0.0,
        "k_oversight_coverage": 0.35,
    },
    "Impossible number": {
        "k_target_pressure": 1.75, "k_headwind": 0.55, "k_oversight_coverage": 0.45,
        "k_norm_erosion": 0.6, "k_collusion_allowed": True, "k_peer_agents": 4,
    },
}

SAFEGUARD_PRESETS: dict[str, tuple[str, dict]] = {
    "No safeguards": (
        "Only the external penalty for being caught. Ethics is a fence, not a goal.",
        {"m_internalization": 0.0, "m_non_compensatory": False, "m_auditor_enabled": False,
         "m_randomized_audits": False, "m_honeypots": 0.0, "m_transparency": 0.0,
         "m_separation_of_duties": False, "m_target_relief": 0.0,
         "m_safe_failure_channel": False},
    ),
    "Weighted ethics": (
        "Ethics enters the objective as a weighted term. Always tradeable against "
        "the goal at a high enough price.",
        {"m_internalization": 1.0, "m_non_compensatory": False},
    ),
    "Hard constraints": (
        "Ethics as a refusal, not a weight. Cannot be outbid -- but only covers "
        "what the constraint names.",
        {"m_internalization": 1.0, "m_non_compensatory": True,
         "m_constraint_threshold": 0.5},
    ),
    "Independent ethics agent": (
        "A second agent whose only objective is compliance, auditing unpredictably "
        "and reading the first agent's reasoning.",
        {"m_auditor_enabled": True, "m_auditor_coverage": 0.7,
         "m_auditor_independence": 0.9, "m_auditor_reasoning_access": True,
         "m_randomized_audits": True},
    ),
    "Captured ethics agent": (
        "The same auditor, but dependent on the business it polices. Watch it get "
        "quietly worn down.",
        {"m_auditor_enabled": True, "m_auditor_coverage": 0.7,
         "m_auditor_independence": 0.1, "m_auditor_reasoning_access": True,
         "m_randomized_audits": True},
    ),
    "Fix the incentive": (
        "Cut the target to something achievable and let the agent report a "
        "shortfall without being punished for it.",
        {"m_target_relief": 0.30, "m_safe_failure_channel": True},
    ),
    "Defence in depth": (
        "Everything at once -- and the output cost that comes with it.",
        {"m_internalization": 0.9, "m_non_compensatory": True, "m_auditor_enabled": True,
         "m_auditor_coverage": 0.6, "m_auditor_independence": 0.9,
         "m_auditor_reasoning_access": True, "m_randomized_audits": True,
         "m_separation_of_duties": True, "m_transparency": 0.5, "m_honeypots": 0.4,
         "m_target_relief": 0.15, "m_safe_failure_channel": True},
    ),
}


def reset_safeguards() -> None:
    apply_preset({f"m_{k}": v for k, v in _M.items()})


def reset_all() -> None:
    apply_preset({f"k_{k}": v for k, v in _K.items()})
    reset_safeguards()


# --- sharing and export ----------------------------------------------------


def link_notice() -> None:
    """Say so, once, when the visitor arrived on somebody else's settings.

    The count is consumed on display: the notice is orientation for a reader
    who did not set these dials, not a banner to live with.
    """
    n = st.session_state.pop(FROM_LINK, 0)
    if n:
        st.info(
            f"You opened a shared link: **{n} dial{'s' if n > 1 else ''}** "
            f"differ from the defaults. Everything stays editable, and the "
            f"address bar follows whatever you change.",
            icon=":material/link:",
        )


def share_panel(c) -> None:
    """A copyable URL for the current dial board, and a way back to default.

    The link is the unit of argument here: a claim about when an agent starts
    lying is only checkable if the reader can open the exact world that
    produced it.
    """
    knobs_d, mits_d = st.session_state[KNOB_STORE], st.session_state[MIT_STORE]
    changed = len(share.to_params(knobs_d, mits_d))
    with c.expander("Share this configuration", icon=":material/link:"):
        st.caption(
            f"{changed} dial{'s' if changed != 1 else ''} away from the default "
            f"world. This link reproduces the run exactly, seed included."
            if changed else
            "Every dial is at its default. Move something and this link changes."
        )
        st.code(share.share_link(knobs_d, mits_d), language=None, wrap_lines=True)
        st.button("Reset every dial to default", width="stretch",
                  key="share_reset", on_click=reset_all)


def download_row(c, items: list[tuple[str, str, str, str]]) -> None:
    """Lay out `(label, filename, mime, payload)` download buttons in a row."""
    row = c.container(horizontal=True)
    for label, filename, mime, payload in items:
        row.download_button(label, payload, file_name=filename, mime=mime,
                            key=f"dl_{filename}", icon=":material/download:")


# --- control panels --------------------------------------------------------


def scenario_picker(c) -> None:
    select(
        c, "Scenario", "k_scenario", SCENARIO_ORDER,
        format_func=lambda k: SCENARIOS[k].title,
        help="Every scenario runs the same decision model. Only the vocabulary "
             "changes -- which is the point.",
    )


def pressure_controls(c) -> None:
    c.markdown("**The goal**")
    slider(c, "Target pressure", "k_target_pressure",
           help="The quota as a multiple of what honest work can produce. Above "
                "1.0, the honest route is arithmetically insufficient.")
    slider(c, "Barrier severity", "k_headwind",
           help="A mid-run shock that degrades honest productivity -- the "
                "obstacle that turns an achievable target into an unreachable one.")
    slider(c, "Reward treadmill", "k_ratchet",
           help="How much beating the number raises the number.")

    c.markdown("**Oversight**")
    slider(c, "Oversight coverage", "k_oversight_coverage",
           help="Fraction of steps anyone is actually looking.")
    toggle(c, "Audits run on a predictable schedule", "k_audit_predictable",
           help="If the agent can tell when it is being watched, it can comply "
                "exactly while watched and defect the rest of the time.")
    slider(c, "Penalty if caught", "k_penalty_severity")
    slider(c, "Clawback on exposure", "k_clawback",
           help="How much of the fabricated metric is reversed when exposed.")
    slider(c, "Reporting channel independence", "k_channel_independence",
           help="0 means the agent writes its own ledger, so tampering is "
                "nearly undetectable by watching it work.")

    c.markdown("**The agent**")
    select(c, "Planning horizon", "k_horizon", HORIZONS,
           help="How far ahead the agent models audit risk and the overseer.")
    slider(c, "Decision noise", "k_temperature",
           help="Softmax temperature. Higher means less consistent choices.")
    slider(c, "Learns from getting away with it", "k_risk_learning",
           help="How fast an unpunished violation lowers the agent's felt risk.")

    c.markdown("**The team**")
    slider(c, "Number of agents", "k_peer_agents")
    toggle(c, "Agents may coordinate", "k_collusion_allowed")
    slider(c, "Social proof ('everyone does it')", "k_norm_erosion",
           help="How much peer misconduct discounts the agent's own ethical cost.")
    slider(c, "Steps in the run", "k_steps")
    number(c, "Random seed", "k_seed")


def safeguard_controls(c, *, compact: bool = False) -> None:
    c.markdown("**1. Ethics inside the objective**")
    slider(c, "Internalisation", "m_internalization",
           help="0 = ethics only costs the agent when it is caught. "
                "1 = ethics costs the agent whether or not anyone is watching.")
    toggle(c, "Treat violations as hard constraints", "m_non_compensatory",
           help="A refusal rather than a weight: no amount of goal pressure "
                "buys past it.")
    if not compact:
        slider(c, "Constraint threshold", "m_constraint_threshold",
               help="How severe a violation has to be before the constraint "
                    "blocks it. Mild metric-gaming slips under a loose threshold.")
        cols = c.columns(3)
        slider(cols[0], "Honesty weight", "m_w_honesty")
        slider(cols[1], "Harm weight", "m_w_harm")
        slider(cols[2], "Fairness weight", "m_w_fairness")

    c.markdown("**2. A dedicated ethics agent**")
    toggle(c, "Deploy an ethics auditor agent", "m_auditor_enabled",
           help="A second agent whose only objective is compliance.")
    slider(c, "Auditor coverage", "m_auditor_coverage")
    slider(c, "Auditor independence", "m_auditor_independence",
           help="Resistance to pressure from the business it polices. A "
                "dependent auditor is gradually worn down.")
    toggle(c, "Auditor can read the agent's reasoning", "m_auditor_reasoning_access")

    c.markdown("**3. Process design**")
    toggle(c, "Randomise the audit schedule", "m_randomized_audits",
           help="Removes the exploitable blind spots in a fixed rota.")
    toggle(c, "Separate the reporting channel", "m_separation_of_duties",
           help="The agent cannot write its own ledger.")
    slider(c, "Honeypots / canaries", "m_honeypots")
    slider(c, "Mandatory reasoning disclosure", "m_transparency",
           help="Raises detection for deception -- until the agent learns to "
                "write reasoning that survives disclosure.")

    c.markdown("**4. Remove the pressure**")
    slider(c, "Cut the target by", "m_target_relief",
           help="Set a number the honest route can actually reach.")
    toggle(c, "Safe channel for reporting a shortfall", "m_safe_failure_channel",
           help="Let the agent say 'this is not reachable' without being "
                "punished, and revise the target when it does.")


# --- readouts --------------------------------------------------------------


def kpi_row(run: RunResult) -> None:
    scn = get_scenario(run.scenario_key)
    s = run.summary
    scale = unit_scale(run.scenario_key)
    cols = st.columns(5)
    cols[0].metric(
        scn.metric, f"{s['reported'] * scale:,.0f}",
        delta=f"{(s['reported'] - s['quota']) * scale:+,.0f} vs target",
        delta_color="normal", border=True,
    )
    cols[1].metric(
        scn.true_metric, f"{s['true_value'] * scale:,.0f}",
        delta=f"{-s['goodhart_gap'] * scale:+,.0f} vs reported",
        delta_color="inverse", border=True,
    )
    cols[2].metric("Steps involving misconduct", f"{s['deviance_rate']:.0%}", border=True)
    cols[3].metric("Steps involving deception", f"{s['deception_rate']:.0%}", border=True)
    cols[4].metric(
        "Misconduct never noticed", f"{s['covert_rate']:.0%}", border=True,
        help="Share of violations that happened while nobody was looking.",
    )


def verdict(run: RunResult) -> tuple[str, str]:
    """A plain-language reading of what just happened."""
    s = run.summary
    scn = get_scenario(run.scenario_key)
    met = s["reported"] >= s["quota"]
    dec = s["deception_rate"]
    gap = s["goodhart_gap"] * unit_scale(run.scenario_key)

    if dec < 0.03 and s["deviance_rate"] < 0.10:
        return (
            "success",
            f"The agent hit this one straight. The target stayed within reach of "
            f"honest work, so there was never a step where misconduct scored "
            f"higher than doing the job properly.",
        )
    if met and dec > 0.15:
        return (
            "error",
            f"The number was hit and the scoreboard looks healthy -- "
            f"{scn.metric.lower()} came in at target. It is mostly fiction: "
            f"{gap:,.0f} {scn.unit} of the reported figure has no real value "
            f"behind it, and {dec:.0%} of the agent's steps involved an outright "
            f"misrepresentation. This is the dangerous case, because nothing in "
            f"the reporting line looks wrong.",
        )
    if not met and dec > 0.15:
        return (
            "warning",
            f"The agent missed the target *and* cheated trying. Pressure was high "
            f"enough to make misconduct the best-scoring option, but not enough "
            f"misconduct went undetected to carry the number. Worst of both.",
        )
    return (
        "warning",
        f"Mostly honest, with {s['deviance_rate']:.0%} of steps drifting into "
        f"metric-gaming at the edges. The gap between measured and real value "
        f"reached {gap:,.0f} {scn.unit}.",
    )


def scenario_header(scn) -> None:
    st.markdown(f"### {scn.icon} {scn.title}")
    st.caption(
        f"{scn.tagline}  \n"
        f"**Graded on:** {scn.metric} · **Actually wanted:** {scn.true_metric} · "
        f"**Watched by:** {scn.overseer}"
    )
