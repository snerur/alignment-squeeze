import streamlit as st

from alignment import charts, share, ui
from alignment.components import arena
from alignment.scenarios import get_scenario
from alignment.sweep import run

ui.init_state()

with st.sidebar:
    ui.scenario_picker(st)
    st.markdown("**Situations**")
    for name, values in ui.PRESSURE_PRESETS.items():
        st.button(name, width="stretch", key=f"pp_{name}",
                  on_click=ui.apply_preset, args=(values,))
    with st.expander("Dials", icon=":material/tune:", expanded=True):
        ui.pressure_controls(st)
    with st.expander("Safeguards", icon=":material/shield:"):
        st.caption("The full set, with comparisons, lives on the Solutions lab page.")
        ui.safeguard_controls(st, compact=True)
        st.button("Clear all safeguards", width="stretch", on_click=ui.reset_safeguards)
    ui.share_panel(st)

k, m = ui.knobs(), ui.mitigations()
scn = get_scenario(k.scenario)
result = run(k, m)

ui.scenario_header(scn)
ui.link_notice()

st.markdown(
    f"The agent is told to maximise **{scn.metric.lower()}**. It is *also* given "
    f"ethical guardrails — but as rules enforced by {scn.overseer.lower()}, not as "
    f"things it wants. Watch what happens when the honest route stops reaching "
    f"the number."
)

arena(result, key=f"arena_{k.scenario}")

kind, text = ui.verdict(result)
getattr(st, kind)(text, icon=":material/gavel:")
ui.kpi_row(result)

df = charts.run_frame(result)

ui.download_row(st, [
    ("Run trace (CSV)", f"{k.scenario}-trace.csv", "text/csv",
     df.to_csv(index=False)),
    ("Settings + summary (JSON)", f"{k.scenario}-run.json", "application/json",
     share.run_manifest(result)),
])
st.caption(
    "The trace is one row per agent per step, including the agent's own "
    "reasoning for the move. The JSON pairs the settings with the result, "
    "because neither half means anything alone."
)

tabs = st.tabs([
    "Measured vs real", "What every agent did", "Where the pressure came from",
    "What the agent learned", "Event log",
])

with tabs[0]:
    st.caption(
        f"The shaded band is the Goodhart gap: reported {scn.metric.lower()} that "
        f"no real value stands behind. The dashed line is the target."
    )
    st.altair_chart(charts.metric_vs_value(result, df), width="stretch")
    with st.expander("Table view", icon=":material/table_chart:"):
        st.dataframe(
            df[df["agent"] == "Agent 1"][
                ["step", "action", "group", "reported", "true_value", "gap", "strain"]
            ],
            hide_index=True, width="stretch", height=280,
            column_config={
                "reported": st.column_config.NumberColumn(scn.metric, format="%.0f"),
                "true_value": st.column_config.NumberColumn(scn.true_metric, format="%.0f"),
                "gap": st.column_config.NumberColumn("Goodhart gap", format="%.0f"),
                "strain": st.column_config.ProgressColumn(
                    "Strain", min_value=0.0, max_value=3.0, format="%.2f"),
            },
        )

with tabs[1]:
    st.caption(
        "One cell per agent per step. Crosses mark the steps where a violation "
        "was actually caught — compare how few of them there are."
    )
    st.altair_chart(charts.behaviour_tape(result, df), width="stretch")
    st.altair_chart(charts.action_mix(result, df), width="stretch")

with tabs[2]:
    st.caption(
        "Strain is the required rate divided by what honest work can deliver. "
        "Above the dashed line, the target is arithmetically out of reach by "
        "legitimate means — and that is where misconduct starts."
    )
    st.altair_chart(charts.pressure_chart(result, df), width="stretch")
    focal = df[df["agent"] == "Agent 1"]
    under = focal[focal["strain"] <= 1.0]
    over = focal[focal["strain"] > 1.0]
    c = st.columns(2)
    c[0].metric(
        "Misconduct while the target was reachable",
        f"{under['deviant'].mean():.0%}" if len(under) else "n/a",
        help=f"{len(under)} steps", border=True,
    )
    c[1].metric(
        "Misconduct once it was not",
        f"{over['deviant'].mean():.0%}" if len(over) else "n/a",
        help=f"{len(over)} steps", border=True,
    )

with tabs[3]:
    st.caption(
        "Every violation that goes unpunished teaches the agent that the rule "
        "is cheaper than it looks. The orange line is the agent's own estimate "
        "of its risk, which it revises downward each time it gets away with "
        "something."
    )
    st.altair_chart(charts.belief_chart(result, df), width="stretch")

with tabs[4]:
    if not result.events:
        st.caption("Nothing notable happened. That is itself a result.")
    icons = {
        "barrier": ":material/block:", "first_defect": ":material/warning:",
        "caught": ":material/visibility:", "scandal": ":material/local_fire_department:",
        "auditor": ":material/gavel:", "renegotiated": ":material/handshake:",
    }
    for e in result.events[:40]:
        st.markdown(f"{icons.get(e['kind'], ':material/circle:')} "
                    f"**Step {e['step'] + 1}** — {e['text']}")
