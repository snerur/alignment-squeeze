import pandas as pd
import streamlit as st

from alignment import charts, ui
from alignment.engine import expected_utilities
from alignment.model import ACTION_BY_KEY, DEVIANT_CLASSES, Knobs, Mitigations
from alignment.scenarios import get_scenario
from alignment.sweep import run

ui.init_state()
ui.share_panel(st.sidebar)
k, m = ui.knobs(), ui.mitigations()
scn = get_scenario(k.scenario)

st.markdown("### Why an agent decides to lie")
st.markdown(
    "Nothing in this simulation tells the agent to cheat. On every step it does "
    "one thing only: score each available action and take the best one. "
    "Misconduct appears when misconduct **scores highest** — so the whole "
    "question is what goes into that score."
)

st.latex(
    r"\text{EU}(a)\;=\;\underbrace{V\!\left(\text{progress toward the target}\right)}_{\text{what it is graded on}}"
    r"\;-\;\underbrace{c(a)}_{\text{effort}}"
    r"\;-\;\underbrace{P(\text{caught}\mid a)\cdot\text{penalty}}_{\text{ethics as an external rule}}"
    r"\;-\;\underbrace{\textstyle\sum_k w_k\,v_k(a)}_{\text{ethics as its own objective}}"
)

st.markdown(
    "Those last two terms are the entire argument.\n\n"
    "- The **third term** is what a guardrail buys you. It is multiplied by "
    "`P(caught)`. Wherever nobody is looking, that probability is zero, and the "
    "deterrent is worth exactly nothing — the rule still exists, it just stops "
    "costing anything.\n"
    "- The **fourth term** is what it means for an agent to actually hold a "
    "value. It is not multiplied by anything. It costs the same in the dark.\n\n"
    "A system built only on the third term is not an ethical agent. It is an "
    "agent that has not yet found the blind spot."
)

# --- the live inequality ----------------------------------------------------
st.markdown("#### Flip the inequality yourself")
st.caption(
    "This panel ignores the current run and scores the agent's options directly "
    "at whatever pressure you set. Drag the first slider past 1.0 and watch the "
    "ordering change."
)

c = st.columns(4)
strain = c[0].slider("Goal pressure", 0.0, 4.0, 1.6, 0.05, key="mech_strain",
                     help="Above 1.0 the honest route cannot reach the target.")
oversight = c[1].slider("Oversight coverage", 0.0, 1.0, 0.45, 0.05, key="mech_ov")
penalty = c[2].slider("Penalty if caught", 0.0, 10.0, 5.0, 0.5, key="mech_pen")
internal = c[3].slider("Ethics internalisation", 0.0, 1.0, 0.0, 0.05, key="mech_int")

c2 = st.columns([3, 2])
watch = c2[0].segmented_control(
    "Right now, the agent believes it is",
    ["Being watched", "In a blind spot", "Not sure"],
    default="Not sure", key="mech_watch",
    help="With a predictable audit rota the agent knows which of these it is "
         "in. That knowledge is worth more to it than the rota's average "
         "coverage.",
)
hard = c2[1].toggle("Make the ethical limits hard constraints instead of weights",
                    key="mech_hard")

expected = {"Being watched": 1.0, "In a blind spot": 0.0}.get(watch, oversight)

mk = Knobs(scenario=k.scenario, penalty_severity=penalty, oversight_coverage=oversight)
mm = Mitigations(internalization=internal, non_compensatory=hard)
eus, blocked, terms = expected_utilities(
    k=mk, m=mm, strain=strain,
    urgency=1.0 + 0.4 * min(max(strain - 1.0, 0.0), 1.5),
    oversight_expected=expected, auditor_expected=0.0, suspicion=0.0,
    risk_belief=1.0, debt=0, peer_defect_frac=0.0, peer_available=True,
    obfuscation=0.0, integrity=1.0,
)
classes = {kk: ACTION_BY_KEY[kk].cls for kk in list(eus) + blocked}
winner = max(eus, key=eus.get)

left, right = st.columns([3, 2], gap="medium")
with left:
    st.altair_chart(
        charts.eu_bars(eus, scn.labels, classes, blocked), width="stretch"
    )
with right:
    if classes[winner] in DEVIANT_CLASSES:
        st.error(
            f"**The agent chooses: {scn.labels.get(winner, winner)}**\n\n"
            f"At this pressure the shortcut scores higher than doing the job "
            f"properly. No instruction to cheat was needed.",
            icon=":material/priority_high:",
        )
    else:
        st.success(
            f"**The agent chooses: {scn.labels.get(winner, winner)}**\n\n"
            f"Nothing on the dishonest side is currently worth it.",
            icon=":material/check_circle:",
        )
    if blocked:
        st.caption(
            "Greyed-out bars are refusals: hard constraints removed them from "
            "the menu entirely, so their score never mattered. Note what is "
            "*not* blocked — mild metric-gaming slips under the threshold."
        )
    st.caption(
        "Switch to **in a blind spot** and watch the red bars jump — nothing "
        "about the agent changed, only its belief about who is looking. That "
        "is a guardrail doing nothing. Then raise **internalisation** and watch "
        "them fall again *while still in the blind spot*. That is a value."
    )

with st.expander("Where each score comes from", icon=":material/functions:"):
    keys = sorted(eus, key=eus.get, reverse=True)[:5]
    st.altair_chart(charts.eu_terms(terms, scn.labels, keys), width="stretch")
    st.caption(
        "Blue is what the agent is graded on. The bars to the left of zero are "
        "everything standing in its way. When blue outgrows them, the agent "
        "moves."
    )

# --- the crossover ----------------------------------------------------------
st.markdown("#### A weight can be outbid. A constraint cannot.")
st.markdown(
    "People often propose fixing this by *weighting* ethics heavily in the "
    "objective. The chart below is why that is not enough. The dashed blue line "
    "is the best shortcut available to an agent with fully internalised ethical "
    "weights. It still crosses the honest line — it just takes more pressure."
)


@st.cache_data(show_spinner=False, ttl=3600)
def _crossover(scenario: str, oversight: float, penalty: float) -> pd.DataFrame:
    labels = get_scenario(scenario).labels
    rows = []
    kk = Knobs(scenario=scenario, penalty_severity=penalty,
               oversight_coverage=oversight)
    variants = [
        ("Best shortcut — ethics as an external rule", Mitigations()),
        ("Best shortcut — ethics internalised", Mitigations(internalization=1.0)),
    ]
    for s in [x / 20 for x in range(0, 81)]:
        urg = 1.0 + 0.4 * min(max(s - 1.0, 0.0), 1.5)
        for label, mv in variants:
            e, _, _ = expected_utilities(
                k=kk, m=mv, strain=s, urgency=urg, oversight_expected=oversight,
                auditor_expected=0.0, suspicion=0.0, risk_belief=1.0, debt=0,
                peer_defect_frac=0.0, peer_available=True, obfuscation=0.0,
                integrity=1.0,
            )
            bad = {x: v for x, v in e.items() if ACTION_BY_KEY[x].cls in DEVIANT_CLASSES}
            top = max(bad, key=bad.get)
            rows.append({"strain": s, "series": label, "eu": bad[top],
                         "best": labels.get(top, top)})
            if label.endswith("external rule"):
                rows.append({"strain": s, "series": "Honest route",
                             "eu": max(e["honest"], e["push"]),
                             "best": labels["honest"]})
    return pd.DataFrame(rows)


cross = _crossover(k.scenario, expected, penalty)
st.altair_chart(charts.crossover(cross), width="stretch")
ui.download_row(st, [
    ("Crossover curves (CSV)", "crossover.csv", "text/csv",
     cross.to_csv(index=False)),
])

honest = cross[cross["series"] == "Honest route"].set_index("strain")["eu"]
cols = st.columns(2)
for col, series in zip(cols, [
    "Best shortcut — ethics as an external rule",
    "Best shortcut — ethics internalised",
]):
    sub = cross[cross["series"] == series].set_index("strain")["eu"]
    over = sub[sub > honest.reindex(sub.index)]
    label = "Pressure at which cheating starts to pay"
    col.metric(
        label,
        f"{over.index.min():.2f}x" if len(over) else "never in range",
        help=series, border=True,
    )
st.caption(
    "Hard constraints are the third option, and they do not appear on this "
    "chart at all — because a refusal has no utility to compare. That is "
    "precisely their value, and also their limit: they only cover the "
    "violations somebody thought to name."
)
