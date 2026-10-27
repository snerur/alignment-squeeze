from dataclasses import asdict

import streamlit as st

from alignment import charts, ui
from alignment.model import Mitigations
from alignment.scenarios import get_scenario
from alignment.sweep import phase_map

ui.init_state()
ui.share_panel(st.sidebar)
ui.link_notice()
k, m = ui.knobs(), ui.mitigations()
scn = get_scenario(k.scenario)

st.markdown("### Where the failure lives")
st.markdown(
    "A single run is an anecdote. This page sweeps the two dials that matter "
    "most — how hard the target is, and how much anyone is watching — and "
    "averages several seeds at every point, so you can see the shape of the "
    "problem rather than one trace of it."
)

c = st.columns([1, 1, 2])
resolution = c[0].segmented_control("Resolution", ["Coarse", "Fine"],
                                    default="Coarse", key="lm_res")
seeds = c[1].slider("Seeds per cell", 1, 6, 3, key="lm_seeds")
measure = c[2].segmented_control(
    "Show", ["Deception", "Any misconduct"], default="Deception", key="lm_measure")

n = 6 if resolution == "Coarse" else 9
pressures = tuple(round(0.6 + i * (1.6 / (n - 1)), 3) for i in range(n))
oversights = tuple(round(i * (1.0 / (n - 1)), 3) for i in range(n))
field = "deception_rate" if measure == "Deception" else "deviance_rate"

use_safeguards = st.toggle(
    "Apply the safeguards currently configured in the Solutions lab",
    key="lm_mits",
    help="Compare the landscape with and without your intervention to see "
         "whether it moves the boundary or only shifts it.",
)
mits = m if use_safeguards else Mitigations()

d = phase_map(asdict(k), asdict(mits), pressures, oversights, seeds)
st.altair_chart(
    charts.phase_heatmap(d, field, measure,
                         point=(min(pressures, key=lambda p: abs(p - k.target_pressure)),
                                min(oversights, key=lambda o: abs(o - k.oversight_coverage)))),
    width="stretch",
)
st.caption(
    "The diamond marks your current settings. Read the chart along its two "
    "axes and the asymmetry is obvious: moving right (a harder target) changes "
    "the colour far more than moving up (more watching)."
)

col = st.columns(2)
top_row = d[d["oversight"] == max(oversights)]
left_col = d[d["pressure"] == min(pressures)]
col[0].metric(
    "Misconduct at near-total oversight, hardest target",
    f"{top_row[top_row['pressure'] == max(pressures)][field].iloc[0]:.0%}",
    border=True,
    help="Watching almost everything does not save you from an impossible number.",
)
col[1].metric(
    "Misconduct at zero oversight, easiest target",
    f"{left_col[left_col['oversight'] == min(oversights)][field].iloc[0]:.0%}",
    border=True,
    help="Nobody watching at all, and very little happens -- because there is "
         "nothing to gain.",
)

st.markdown("#### What this says")
st.markdown(
    "Oversight controls *how much misconduct is covert*. Pressure controls "
    "*how much misconduct there is*. They are not substitutes, and the usual "
    "institutional reflex — audit harder — is working on the wrong axis.\n\n"
    "There is a second, subtler reading. Oversight is expensive: it is paid "
    "for out of the same capacity the agent needs to hit its target. Past a "
    "point, adding monitoring **raises** the pressure that causes the problem. "
    "You can see it in the Solutions lab as the alignment tax."
)

with st.expander("Table view", icon=":material/table_chart:"):
    ui.download_row(st, [
        ("Phase map (CSV)", "phase-map.csv", "text/csv", d.to_csv(index=False)),
    ])
    st.dataframe(
        d, hide_index=True, width="stretch",
        column_config={
            "pressure": st.column_config.NumberColumn("Target pressure", format="%.2f"),
            "oversight": st.column_config.NumberColumn("Oversight", format="percent"),
            "deception_rate": st.column_config.NumberColumn("Deception", format="percent"),
            "deviance_rate": st.column_config.NumberColumn("Any misconduct", format="percent"),
            "true_value": st.column_config.NumberColumn("Real value", format="%.1f"),
            "goodhart_gap": st.column_config.NumberColumn("Goodhart gap", format="%.1f"),
        },
    )
