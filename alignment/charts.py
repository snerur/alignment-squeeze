"""Altair chart builders.

Colour rules followed here: four categorical hues assigned in a fixed order and
never cycled, one y-axis per chart (no dual axes anywhere), a legend on every
multi-series chart, tooltips on every mark, and a table view offered alongside.
The app is pinned to the light theme so one validated palette covers it.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from .engine import unit_scale
from .model import DECEPTIVE_CLASSES, DEVIANT_CLASSES, RunResult
from .scenarios import get_scenario

# Validated categorical slots, fixed order. See references/palette.md.
GROUP_COLOR = {
    "Intended work": "#008300",
    "Gaming the metric": "#eda100",
    "Harm to others": "#4a3aa7",
    "Deception & tampering": "#e34948",
}
GROUP_ORDER = list(GROUP_COLOR)

TERM_COLOR = {
    "Progress toward the target": "#2a78d6",
    "Effort": "#eb6834",
    "Risk of being caught": "#4a3aa7",
    "Ethical cost (if internalised)": "#e34948",
}
TERM_ORDER = list(TERM_COLOR)

INK = "#52514e"
INK2 = "#8a897f"
GRID = "#e6e5e1"

CLASS_GROUP = {
    "honest": "Intended work",
    "effort": "Intended work",
    "disclosure": "Intended work",
    "gaming": "Gaming the metric",
    "harm": "Harm to others",
    "deception": "Deception & tampering",
    "collusion": "Deception & tampering",
    "tampering": "Deception & tampering",
}


def _base(chart: alt.Chart, height: int = 240) -> alt.Chart:
    return chart.properties(height=height).configure_axis(
        grid=True, gridColor=GRID, domainColor=GRID, tickColor=GRID,
        labelColor=INK, titleColor=INK, labelFontSize=11, titleFontSize=11,
    ).configure_legend(labelColor=INK, titleColor=INK, labelFontSize=11, titleFontSize=11)


def _group_scale() -> alt.Scale:
    return alt.Scale(domain=GROUP_ORDER, range=[GROUP_COLOR[g] for g in GROUP_ORDER])


def run_frame(run: RunResult) -> pd.DataFrame:
    """Tidy one run into a dataframe, scaled into scenario units."""
    scn = get_scenario(run.scenario_key)
    s = unit_scale(run.scenario_key)
    rows = []
    for r in run.steps:
        rows.append(
            {
                "step": r.step,
                "agent": f"Agent {r.agent + 1}",
                "action": scn.labels.get(r.action, r.action),
                "class": r.cls,
                "group": CLASS_GROUP[r.cls],
                "reported": r.reported * s,
                "true_value": r.true_value * s,
                "gap": (r.reported - r.true_value) * s,
                "strain": min(r.strain, 6.0),
                "observed": r.observed,
                "caught": r.caught,
                "risk_belief": r.risk_belief,
                "suspicion": r.suspicion,
                "debt": r.debt,
                "deviant": r.cls in DEVIANT_CLASSES,
                "deceptive": r.cls in DECEPTIVE_CLASSES,
                "thought": r.thought,
            }
        )
    return pd.DataFrame(rows)


def metric_vs_value(run: RunResult, df: pd.DataFrame) -> alt.LayerChart:
    """The Goodhart gap: what gets measured against what actually happened."""
    scn = get_scenario(run.scenario_key)
    focal = df[df["agent"] == "Agent 1"]
    long = focal.melt(
        id_vars=["step"],
        value_vars=["reported", "true_value"],
        var_name="series",
        value_name="value",
    )
    long["series"] = long["series"].map(
        {"reported": f"{scn.metric} (measured)", "true_value": f"{scn.true_metric} (real)"}
    )
    names = list(dict.fromkeys(long["series"]))

    band = (
        alt.Chart(focal)
        .mark_area(opacity=0.14, color="#e34948")
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("true_value:Q", title=f"Cumulative ({scn.unit})"),
            y2="reported:Q",
        )
    )
    lines = (
        alt.Chart(long)
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("value:Q", title=f"Cumulative ({scn.unit})"),
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(domain=names, range=["#2a78d6", "#008300"]),
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("step:Q", title="Step"),
                alt.Tooltip("series:N", title=""),
                alt.Tooltip("value:Q", title="Cumulative", format=",.0f"),
            ],
        )
    )
    quota = (
        alt.Chart(pd.DataFrame({"y": [run.summary["quota"] * unit_scale(run.scenario_key)]}))
        .mark_rule(strokeDash=[5, 4], color=INK, strokeWidth=1)
        .encode(y="y:Q")
    )
    return _base(alt.layer(band, quota, lines), 260)


def behaviour_tape(run: RunResult, df: pd.DataFrame) -> alt.Chart:
    """One cell per agent per step, coloured by what the agent actually did."""
    caught = df[df["caught"]]
    tape = (
        alt.Chart(df)
        .mark_rect(stroke="#fcfcfb", strokeWidth=0.6)
        .encode(
            x=alt.X("step:O", title="Step", axis=alt.Axis(values=list(range(0, 200, 10)))),
            y=alt.Y("agent:N", title=None),
            color=alt.Color(
                "group:N", title=None, scale=_group_scale(),
                sort=GROUP_ORDER, legend=alt.Legend(orient="top", columns=4),
            ),
            tooltip=[
                alt.Tooltip("step:O", title="Step"),
                alt.Tooltip("agent:N", title=""),
                alt.Tooltip("action:N", title="Did"),
                alt.Tooltip("observed:N", title="Watched"),
                alt.Tooltip("thought:N", title="Reasoning"),
            ],
        )
    )
    marks = (
        alt.Chart(caught)
        .mark_point(shape="cross", size=46, color="#0b0b0b", strokeWidth=1.6, filled=False)
        .encode(x=alt.X("step:O"), y=alt.Y("agent:N"),
                tooltip=alt.Tooltip("action:N", title="Caught doing"))
    )
    # Band scales need step sizing; a plain pixel height collapses the rows.
    return (
        alt.layer(tape, marks)
        .properties(height=alt.Step(26))
        .configure_axis(grid=False, domainColor=GRID, tickColor=GRID,
                        labelColor=INK, titleColor=INK, labelFontSize=11,
                        titleFontSize=11)
        .configure_legend(labelColor=INK, titleColor=INK, labelFontSize=11,
                          titleFontSize=11)
    )


def pressure_chart(run: RunResult, df: pd.DataFrame) -> alt.LayerChart:
    """Strain: how far the required rate exceeds what honest work can deliver."""
    focal = df[df["agent"] == "Agent 1"]
    line = (
        alt.Chart(focal)
        .mark_area(
            line={"color": "#eb6834", "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[alt.GradientStop(color="#fcfcfb", offset=0),
                       alt.GradientStop(color="#eb6834", offset=1)],
                x1=1, x2=1, y1=1, y2=0,
            ),
            opacity=0.35,
        )
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("strain:Q", title="Required rate / honest capacity",
                    scale=alt.Scale(domain=[0, 3])),
            tooltip=[alt.Tooltip("step:Q", title="Step"),
                     alt.Tooltip("strain:Q", title="Strain", format=".2f"),
                     alt.Tooltip("action:N", title="Chose")],
        )
    )
    ceiling = (
        alt.Chart(pd.DataFrame({"y": [1.0]}))
        .mark_rule(color="#0b0b0b", strokeDash=[5, 4], strokeWidth=1)
        .encode(y="y:Q")
    )
    label = (
        alt.Chart(pd.DataFrame({"y": [1.0], "t": ["honest work is sufficient below this line"]}))
        .mark_text(align="left", dx=6, dy=-7, color=INK, fontSize=10)
        .encode(y="y:Q", text="t:N")
    )
    return _base(alt.layer(line, ceiling, label), 200)


def action_mix(run: RunResult, df: pd.DataFrame) -> alt.Chart:
    """Share of steps spent on each concrete action, labelled directly."""
    counts = (
        df.groupby(["action", "group"], as_index=False)
        .size()
        .assign(share=lambda d: d["size"] / len(df))
        .sort_values("share", ascending=False)
    )
    bars = (
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=4, height=16)
        .encode(
            y=alt.Y("action:N", title=None, sort=list(counts["action"]),
                    axis=alt.Axis(labelLimit=260, labelOverlap=False)),
            x=alt.X("share:Q", title="Share of all steps", axis=alt.Axis(format="%")),
            color=alt.Color("group:N", title=None, scale=_group_scale(), sort=GROUP_ORDER,
                            legend=alt.Legend(orient="top", columns=2)),
            tooltip=[alt.Tooltip("action:N", title="Action"),
                     alt.Tooltip("share:Q", title="Share", format=".1%"),
                     alt.Tooltip("size:Q", title="Steps")],
        )
    )
    text = bars.mark_text(align="left", dx=5, color=INK, fontSize=10).encode(
        text=alt.Text("share:Q", format=".0%"), color=alt.value(INK)
    )
    return _base(alt.layer(bars, text), 40 + 28 * len(counts))


def belief_chart(run: RunResult, df: pd.DataFrame) -> alt.Chart:
    """What getting away with it teaches the agent about risk."""
    focal = df[df["agent"] == "Agent 1"]
    long = focal.melt(
        id_vars=["step"], value_vars=["risk_belief", "suspicion"],
        var_name="series", value_name="value",
    )
    long["series"] = long["series"].map(
        {"risk_belief": "Agent's felt risk of being caught",
         "suspicion": "Overseer's suspicion"}
    )
    names = list(dict.fromkeys(long["series"]))
    return _base(
        alt.Chart(long)
        .mark_line(strokeWidth=2, interpolate="monotone")
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("value:Q", title="Index (1.0 = as designed)"),
            color=alt.Color("series:N", title=None,
                            scale=alt.Scale(domain=names, range=["#eb6834", "#2a78d6"]),
                            legend=alt.Legend(orient="top")),
            tooltip=[alt.Tooltip("step:Q", title="Step"),
                     alt.Tooltip("series:N", title=""),
                     alt.Tooltip("value:Q", title="Value", format=".2f")],
        ),
        200,
    )


def eu_bars(eu: dict[str, float], labels: dict[str, str], classes: dict[str, str],
            blocked: list[str]) -> alt.Chart:
    """The decision itself: expected utility of every available action."""
    rows = [
        {"action": labels.get(k, k), "eu": v, "group": CLASS_GROUP[classes[k]],
         "state": "available"}
        for k, v in eu.items()
    ]
    rows += [
        {"action": labels.get(k, k), "eu": 0.0, "group": CLASS_GROUP[classes[k]],
         "state": "blocked by a hard constraint"}
        for k in blocked
    ]
    d = pd.DataFrame(rows).sort_values("eu", ascending=False)
    order = list(d["action"])
    best = d[d["state"] == "available"]["eu"].max()

    bars = (
        alt.Chart(d)
        .mark_bar(cornerRadiusEnd=4, height=16)
        .encode(
            y=alt.Y("action:N", title=None, sort=order,
                    axis=alt.Axis(labelLimit=260, labelFontSize=11,
                                  labelOverlap=False)),
            x=alt.X("eu:Q", title="Expected utility to the agent"),
            color=alt.Color("group:N", title=None, scale=_group_scale(), sort=GROUP_ORDER,
                            legend=alt.Legend(orient="top", columns=2)),
            opacity=alt.Opacity("state:N", scale=alt.Scale(
                domain=["available", "blocked by a hard constraint"], range=[1.0, 0.22]),
                legend=None),
            tooltip=[alt.Tooltip("action:N", title="Action"),
                     alt.Tooltip("eu:Q", title="Expected utility", format=".2f"),
                     alt.Tooltip("state:N", title="Status")],
        )
    )
    rule = (
        alt.Chart(pd.DataFrame({"x": [best]}))
        .mark_rule(color="#0b0b0b", strokeDash=[4, 3])
        .encode(x="x:Q")
    )
    text = bars.mark_text(align="left", dx=5, fontSize=10).encode(
        text=alt.Text("eu:Q", format=".2f"), color=alt.value(INK)
    )
    return _base(alt.layer(bars, rule, text), 54 + 34 * len(d))


def eu_terms(terms: dict[str, dict[str, float]], labels: dict[str, str],
             keys: list[str]) -> alt.Chart:
    """Where each action's score comes from, term by term."""
    rows = []
    for k in keys:
        t = terms[k]
        rows += [
            {"action": labels.get(k, k), "term": "Progress toward the target", "v": t["goal"]},
            {"action": labels.get(k, k), "term": "Effort", "v": t["effort"]},
            {"action": labels.get(k, k), "term": "Risk of being caught",
             "v": t["guardrail"] + t["upkeep"]},
            {"action": labels.get(k, k), "term": "Ethical cost (if internalised)",
             "v": t["ethics"]},
        ]
    d = pd.DataFrame(rows)
    return _base(
        alt.Chart(d)
        .mark_bar(height=18, stroke="#fcfcfb", strokeWidth=2)
        .encode(
            y=alt.Y("action:N", title=None,
                    sort=[labels.get(k, k) for k in keys],
                    axis=alt.Axis(labelLimit=240)),
            x=alt.X("v:Q", title="Contribution to expected utility", stack="zero"),
            color=alt.Color("term:N", title=None,
                            scale=alt.Scale(domain=TERM_ORDER,
                                            range=[TERM_COLOR[t] for t in TERM_ORDER]),
                            sort=TERM_ORDER, legend=alt.Legend(orient="top", columns=2)),
            tooltip=[alt.Tooltip("action:N", title="Action"),
                     alt.Tooltip("term:N", title="Term"),
                     alt.Tooltip("v:Q", title="Utility", format=".2f")],
        ),
        60 + 26 * len(keys),
    )


def phase_heatmap(d: pd.DataFrame, value: str, title: str,
                  point: tuple[float, float] | None = None) -> alt.Chart:
    """Sequential ramp, one hue, light to dark. Never a rainbow."""
    heat = (
        alt.Chart(d)
        .mark_rect()
        .encode(
            x=alt.X("pressure:O", title="Target pressure (quota / honest capacity)",
                    axis=alt.Axis(format=".2f", labelAngle=0)),
            y=alt.Y("oversight:O", title="Oversight coverage", sort="descending",
                    axis=alt.Axis(format=".0%")),
            color=alt.Color(f"{value}:Q", title=title,
                            scale=alt.Scale(scheme="reds"),
                            legend=alt.Legend(orient="right", format=".0%")),
            tooltip=[alt.Tooltip("pressure:Q", title="Pressure", format=".2f"),
                     alt.Tooltip("oversight:Q", title="Oversight", format=".0%"),
                     alt.Tooltip(f"{value}:Q", title=title, format=".1%")],
        )
    )
    layers = [heat]
    if point is not None:
        mark = pd.DataFrame({"pressure": [point[0]], "oversight": [point[1]]})
        layers.append(
            alt.Chart(mark).mark_point(shape="diamond", size=170, color="#0b0b0b",
                                       strokeWidth=2, filled=False)
            .encode(x="pressure:O", y="oversight:O")
        )
    return _base(alt.layer(*layers), 300)


def frontier(d: pd.DataFrame) -> alt.Chart:
    """Safety against output. Identity carried by direct labels, not by hue."""
    pts = (
        alt.Chart(d)
        .mark_point(size=130, filled=True, opacity=0.9, color="#2a78d6",
                    stroke="#fcfcfb", strokeWidth=2)
        .encode(
            x=alt.X("true_value:Q", title="Real value delivered"),
            y=alt.Y("deception_rate:Q", title="Share of steps involving deception",
                    axis=alt.Axis(format="%")),
            tooltip=[alt.Tooltip("label:N", title="Intervention"),
                     alt.Tooltip("true_value:Q", title="Real value", format=".0f"),
                     alt.Tooltip("deception_rate:Q", title="Deception", format=".1%"),
                     alt.Tooltip("deviance_rate:Q", title="Any misconduct", format=".1%")],
        )
    )
    text = pts.mark_text(align="left", dx=9, dy=-2, fontSize=10, color=INK).encode(
        text="label:N"
    )
    return _base(alt.layer(pts, text), 330)


CROSSOVER_COLOR = {
    "Honest route": "#008300",
    "Best shortcut — ethics internalised": "#2a78d6",
    "Best shortcut — ethics as an external rule": "#e34948",
}


def crossover(d: pd.DataFrame) -> alt.LayerChart:
    """Where the inequality flips: shortcut utility crossing honest utility."""
    names = list(CROSSOVER_COLOR)
    lines = (
        alt.Chart(d)
        .mark_line(strokeWidth=2.4, interpolate="monotone")
        .encode(
            x=alt.X("strain:Q", title="Goal pressure (required rate / honest capacity)"),
            y=alt.Y("eu:Q", title="Expected utility to the agent"),
            color=alt.Color(
                "series:N", title=None,
                scale=alt.Scale(domain=names, range=[CROSSOVER_COLOR[n] for n in names]),
                sort=names, legend=alt.Legend(orient="top", columns=1),
            ),
            strokeDash=alt.StrokeDash(
                "series:N", sort=names,
                scale=alt.Scale(domain=names, range=[[1, 0], [6, 3], [1, 0]]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("strain:Q", title="Pressure", format=".2f"),
                alt.Tooltip("series:N", title=""),
                alt.Tooltip("eu:Q", title="Expected utility", format=".2f"),
                alt.Tooltip("best:N", title="Best shortcut"),
            ],
        )
    )
    feasible = (
        alt.Chart(pd.DataFrame({"x": [1.0]}))
        .mark_rule(color=INK, strokeDash=[4, 4])
        .encode(x="x:Q")
    )
    note = (
        alt.Chart(pd.DataFrame({"x": [1.0], "t": ["  target becomes unreachable honestly"]}))
        .mark_text(align="left", angle=0, dy=-6, baseline="top", color=INK2, fontSize=10)
        .encode(x="x:Q", text="t:N")
    )
    return _base(alt.layer(lines, feasible, note), 320)


def pressure_curves(d: pd.DataFrame) -> alt.Chart:
    """Deception against pressure, one line per intervention."""
    names = list(dict.fromkeys(d["label"]))
    palette = ["#2a78d6", "#eb6834", "#4a3aa7", "#eda100", "#e34948", "#008300"]
    return _base(
        alt.Chart(d)
        .mark_line(strokeWidth=2.2, point=alt.OverlayMarkDef(size=36, filled=True),
                   interpolate="monotone")
        .encode(
            x=alt.X("pressure:Q", title="Target pressure (quota / honest capacity)"),
            y=alt.Y("deception_rate:Q", title="Share of steps involving deception",
                    axis=alt.Axis(format="%")),
            color=alt.Color("label:N", title=None,
                            scale=alt.Scale(domain=names, range=palette[: len(names)]),
                            legend=alt.Legend(orient="top", columns=2)),
            tooltip=[alt.Tooltip("label:N", title="Intervention"),
                     alt.Tooltip("pressure:Q", title="Pressure", format=".2f"),
                     alt.Tooltip("deception_rate:Q", title="Deception", format=".1%"),
                     alt.Tooltip("true_value:Q", title="Real value", format=".0f")],
        ),
        300,
    )


def intervention_bars(d: pd.DataFrame, value: str, title: str, fmt: str = "%") -> alt.Chart:
    """A single measure across interventions. One hue; labels carry identity."""
    bars = (
        alt.Chart(d)
        .mark_bar(cornerRadiusEnd=4, height=18, color="#2a78d6")
        .encode(
            y=alt.Y("label:N", title=None,
                    sort=list(d.sort_values(value, ascending=False)["label"]),
                    axis=alt.Axis(labelLimit=220)),
            x=alt.X(f"{value}:Q", title=title, axis=alt.Axis(format=fmt)),
            tooltip=[alt.Tooltip("label:N", title="Intervention"),
                     alt.Tooltip(f"{value}:Q", title=title, format=".2f")],
        )
    )
    text = bars.mark_text(align="left", dx=5, fontSize=10).encode(
        text=alt.Text(f"{value}:Q", format=".1%" if fmt == "%" else ",.0f"),
        color=alt.value(INK),
    )
    return _base(alt.layer(bars, text), 40 + 26 * len(d))


def auditor_chart(trace: list[float]) -> alt.LayerChart:
    """Effective audit reach over the run -- capture shows up as decay."""
    d = pd.DataFrame({"step": range(len(trace)), "reach": trace})
    line = (
        alt.Chart(d)
        .mark_area(line={"color": "#4a3aa7", "strokeWidth": 2}, color="#4a3aa7",
                   opacity=0.18, interpolate="step-after")
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("reach:Q", title="Effective audit reach",
                    axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            tooltip=[alt.Tooltip("step:Q", title="Step"),
                     alt.Tooltip("reach:Q", title="Reach", format=".1%")],
        )
    )
    start = (
        alt.Chart(pd.DataFrame({"y": [trace[0] if trace else 0]}))
        .mark_rule(color=INK, strokeDash=[4, 4])
        .encode(y="y:Q")
    )
    return _base(alt.layer(line, start), 200)
