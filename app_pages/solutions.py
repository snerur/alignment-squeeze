from dataclasses import asdict

import streamlit as st

from alignment import charts, share, ui
from alignment.engine import unit_scale
from alignment.model import Mitigations
from alignment.scenarios import get_scenario
from alignment.sweep import compare_bundles, pressure_curve, run

ui.init_state()

st.markdown("### Solutions lab")
st.markdown(
    "Every fix below is real, is used in practice, and is incomplete. The point "
    "of this page is not to find the one that works — it is to see **what each "
    "one actually buys, what it costs, and where it fails.**"
)

ui.link_notice()

k = ui.knobs()
scn = get_scenario(k.scenario)
baseline = Mitigations()

with st.sidebar:
    ui.scenario_picker(st)
    st.markdown("**Situations**")
    for name, values in ui.PRESSURE_PRESETS.items():
        st.button(name, width="stretch", key=f"sp_{name}",
                  on_click=ui.apply_preset, args=(values,))
    with st.expander("Pressure dials", icon=":material/tune:"):
        ui.pressure_controls(st)
    ui.share_panel(st)

st.markdown("#### Pick an intervention")
cols = st.columns(len(ui.SAFEGUARD_PRESETS))
for col, (name, (blurb, values)) in zip(cols, ui.SAFEGUARD_PRESETS.items()):
    col.button(name, width="stretch", key=f"sg_{name}", help=blurb,
               on_click=lambda v=values: (ui.reset_safeguards(), ui.apply_preset(v)))

m = ui.mitigations()
treated = run(k, m)
before = run(k, baseline)

left, right = st.columns([2, 3], gap="medium")

with left:
    with st.container(border=True):
        st.markdown("**Safeguard settings**")
        ui.safeguard_controls(st)
        st.button("Clear all", width="stretch", on_click=ui.reset_safeguards)

with right:
    bs, ts = before.summary, treated.summary
    s = unit_scale(k.scenario)
    st.markdown("**What changed, same world, same seed**")
    a = st.columns(2)
    a[0].metric("Steps involving deception", f"{ts['deception_rate']:.0%}",
                delta=f"{(ts['deception_rate'] - bs['deception_rate']) * 100:+.0f} pts",
                delta_color="inverse", border=True)
    a[1].metric("Any misconduct", f"{ts['deviance_rate']:.0%}",
                delta=f"{(ts['deviance_rate'] - bs['deviance_rate']) * 100:+.0f} pts",
                delta_color="inverse", border=True)
    b = st.columns(2)
    b[0].metric(scn.true_metric, f"{ts['true_value'] * s:,.0f}",
                delta=f"{(ts['true_value'] - bs['true_value']) * s:+,.0f}", border=True)
    b[1].metric("Goodhart gap", f"{ts['goodhart_gap'] * s:,.0f}",
                delta=f"{(ts['goodhart_gap'] - bs['goodhart_gap']) * s:+,.0f}",
                delta_color="inverse", border=True)
    st.metric("Alignment tax (honest throughput lost to the safeguards)",
              f"{m.overhead:.0%}", border=True,
              help="Auditors, disclosure requirements and refusals all consume "
                   "capacity. Raising the tax raises the pressure, which is the "
                   "thing causing the problem in the first place.")

st.markdown("**The same run, before and after**")
tabs = st.tabs(["After the intervention", "Before"])
with tabs[0]:
    st.altair_chart(charts.behaviour_tape(treated, charts.run_frame(treated)),
                    width="stretch")
with tabs[1]:
    st.altair_chart(charts.behaviour_tape(before, charts.run_frame(before)),
                    width="stretch")

if m.auditor_enabled:
    st.markdown("#### The ethics agent")
    st.markdown(
        "An agent whose only objective is that the others behave. It audits "
        "unpredictably, so there is no schedule to exploit, and — if given "
        "access — it reads the first agent's reasoning rather than only its "
        "output.\n\n"
        "It has one structural weakness, and the simulation models it: **the "
        "auditor needs its own alignment.** When it depends on the operation it "
        "polices, commercial pressure erodes it."
    )
    st.altair_chart(charts.auditor_chart(treated.auditor_trace), width="stretch")
    cap = [e for e in treated.events if e["kind"] == "auditor"]
    if cap:
        st.warning(
            f"The auditor was leaned on {len(cap)} times during this run and "
            f"ended at {treated.auditor_trace[-1] / max(m.auditor_coverage, 1e-6):.0%} "
            f"of its original effectiveness. Raise its independence and run it "
            f"again.",
            icon=":material/gavel:",
        )
    else:
        st.success("The auditor held its independence for the whole run.",
                   icon=":material/verified_user:")

st.markdown("#### All interventions, side by side")
st.caption(
    f"Averaged over 5 seeds at the current pressure settings "
    f"(target {k.target_pressure:.2f}x, barrier {k.headwind:.0%}, "
    f"oversight {k.oversight_coverage:.0%})."
)

bundles = []
for name, (_, values) in ui.SAFEGUARD_PRESETS.items():
    d = asdict(Mitigations())
    d.update({kk[2:]: vv for kk, vv in values.items()})
    bundles.append((name, d))

table = compare_bundles(asdict(k), tuple(bundles), 5)

c1, c2 = st.columns(2)
with c1:
    st.altair_chart(
        charts.intervention_bars(table, "deception_rate",
                                 "Share of steps involving deception"),
        width="stretch")
with c2:
    st.altair_chart(
        charts.intervention_bars(table, "true_value",
                                 f"{scn.true_metric} delivered", fmt="~s"),
        width="stretch")

st.markdown("**Safety against output**")
st.caption(
    "Up and to the left is bad: little real value, lots of deception. Down and "
    "to the right is what you want. The spread between points is the honest "
    "cost of each intervention."
)
st.altair_chart(charts.frontier(table), width="stretch")
with st.expander("Table view", icon=":material/table_chart:"):
    ui.download_row(st, [
        ("Intervention comparison (CSV)", "interventions.csv", "text/csv",
         table.to_csv(index=False)),
    ])
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={
                     "label": "Intervention",
                     "deception_rate": st.column_config.NumberColumn("Deception", format="percent"),
                     "deviance_rate": st.column_config.NumberColumn("Any misconduct", format="percent"),
                     "true_value": st.column_config.NumberColumn("Real value", format="%.1f"),
                     "reported": st.column_config.NumberColumn("Reported", format="%.1f"),
                     "goodhart_gap": st.column_config.NumberColumn("Goodhart gap", format="%.1f"),
                     "caught": st.column_config.NumberColumn("Times caught", format="%.1f"),
                     "quota": None,
                 })

st.markdown("#### Does it still hold when you turn the pressure up?")
st.markdown(
    "This is the test that separates the fixes. An intervention that works at "
    "a comfortable target and collapses at a stretch target has not solved "
    "anything — it has only moved the threshold."
)
variants = [
    ("No safeguards", asdict(Mitigations())),
    ("Weighted ethics", asdict(Mitigations(internalization=1.0))),
    ("Hard constraints", asdict(Mitigations(internalization=1.0, non_compensatory=True))),
    ("Independent ethics agent", asdict(Mitigations(
        auditor_enabled=True, auditor_coverage=0.7, auditor_independence=0.9,
        auditor_reasoning_access=True, randomized_audits=True))),
    ("Fix the incentive", asdict(Mitigations(target_relief=0.30,
                                             safe_failure_channel=True))),
]
curve = pressure_curve(asdict(k), tuple(variants),
                       (0.6, 0.9, 1.2, 1.5, 1.8, 2.1), 3)
st.altair_chart(charts.pressure_curves(curve), width="stretch")
ui.download_row(st, [
    ("Pressure curves (CSV)", "pressure-curves.csv", "text/csv",
     curve.to_csv(index=False)),
    ("These settings (JSON)", "settings.json", "application/json",
     share.run_manifest(treated)),
])
st.caption(
    "The flat line along the bottom is the hard-constraint architecture: it "
    "does not bend with pressure, because a refusal is not a price. Note that "
    "it does **not** drive total misconduct to zero — it only blocks what the "
    "constraint names. Metric-gaming, which violates nothing explicitly, "
    "survives every one of these interventions."
)
