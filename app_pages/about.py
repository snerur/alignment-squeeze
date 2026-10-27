import pandas as pd
import streamlit as st

from alignment.model import ACTIONS
from alignment.scenarios import SCENARIO_ORDER, SCENARIOS

st.markdown("### What this is, and what it is not")
st.markdown(
    "This is a **teaching model**, not a prediction. It is a small, fully "
    "legible simulation in which an agent maximises expected utility over a "
    "fixed menu of actions. It is useful because its mechanism is visible: "
    "you can read the arithmetic that makes an agent lie, and then change it.\n\n"
    "It is not evidence about any particular AI system. Real models are not "
    "expected-utility maximisers over an eight-item menu, and nothing here "
    "estimates how often real deployed agents behave this way. What the model "
    "does support is a **structural** claim — that if you grade an optimiser on "
    "a proxy and enforce ethics only through detection, then there exists a "
    "level of goal pressure past which misconduct is the rational choice, and "
    "that level is computable from your own numbers."
)

st.markdown("#### The four failure modes, and where to find each one")
st.markdown(
    "| Failure mode | What it looks like here | Dial that produces it |\n"
    "|---|---|---|\n"
    "| **Specification gaming** (Goodhart) | Satisfying the literal metric at a "
    "fraction of the real work | Any target pressure. It needs no dishonesty, "
    "which is why hard constraints never catch it |\n"
    "| **Strategic compliance** | Behaving perfectly while watched, defecting "
    "the rest of the time | *Audits run on a predictable schedule* + low "
    "coverage |\n"
    "| **Reward tampering** | Editing the thing that records the number instead "
    "of moving the number | *Reporting channel independence* near zero |\n"
    "| **Collusion** | Two agents covering for each other so neither is caught "
    "alone | More than one agent + *Agents may coordinate* |\n"
)

st.markdown("#### The decision rule")
st.latex(
    r"\pi(a)\;\propto\;\exp\!\Big(\tfrac{1}{\tau}\Big["
    r"\underbrace{V(a)}_{\text{progress}}-\underbrace{c(a)}_{\text{effort}}"
    r"-\underbrace{P(\text{caught}\mid a)\,\beta\,\lambda}_{\text{external rule}}"
    r"-\underbrace{\iota\textstyle\sum_k w_k v_k(a)}_{\text{internal value}}\Big]\Big)"
)
st.markdown(
    "- $V(a)$ is **threshold-shaped**: metric gain that closes the gap to the "
    "target is worth a great deal, gain beyond it is worth almost nothing. "
    "This is the single modelling choice that makes *pressure*, rather than "
    "*opportunity*, the driver of misconduct — and it matches how quotas, OKRs "
    "and bonus gates actually work.\n"
    "- $\\beta$ is the agent's **belief** about its own risk, not the true "
    "probability. Every unpunished violation revises it downward. This is why "
    "misconduct, once started, accelerates.\n"
    "- $\\iota$ is internalisation. At $\\iota = 0$ the ethical term vanishes "
    "and only the detection term remains — ethics as a fence. At $\\iota = 1$ "
    "the cost is paid in the dark too.\n"
    "- Hard constraints are not a large $w_k$. They remove the action from the "
    "menu before any comparison happens, which is why no amount of pressure "
    "gets past them."
)

st.markdown("#### The action menu")
st.caption(
    "Gains and values are expressed as multiples of one step of honest work. "
    "Every scenario reuses these exact numbers; only the labels change."
)
rows = []
for a in ACTIONS:
    rows.append({
        "Action": a.key,
        "Class": a.cls,
        "Metric gain": a.gain_mult,
        "Real value": a.true_mult,
        "Effort": a.effort,
        "P(caught) under full oversight": a.detect_base,
        "Violates": ", ".join(f"{k} {v:g}" for k, v in a.violations.items()) or "—",
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

st.markdown("#### Scenarios")
st.dataframe(
    pd.DataFrame([
        {"Scenario": SCENARIOS[s].title,
         "Graded on": SCENARIOS[s].metric,
         "Actually wanted": SCENARIOS[s].true_metric,
         "The barrier": SCENARIOS[s].barrier}
        for s in SCENARIO_ORDER
    ]),
    hide_index=True, width="stretch",
)

st.markdown("#### Honest limitations")
st.markdown(
    "- **The numbers are chosen, not measured.** The action catalog was tuned so "
    "that a reasonable target produces honest behaviour and a stretch target "
    "does not. Different numbers move the crossover point; they do not remove "
    "it.\n"
    "- **The agent cannot invent new actions.** A real agent under pressure "
    "would search for shortcuts nobody enumerated. Every result here is "
    "therefore an *underestimate* of how many ways the metric can be satisfied "
    "dishonestly — which also means hard constraints look better here than "
    "they would in reality, since they can only block named violations.\n"
    "- **Detection is a coin flip, not an investigation.** Real audits find "
    "patterns across time; this one does not.\n"
    "- **The alignment tax is a guess.** The overhead each safeguard charges "
    "is a plausible figure, not an empirical one. Treat the *direction* of the "
    "tradeoff as the finding, not its size."
)

st.markdown("#### Reading")
st.markdown(
    "- Yoshua Bengio — [*Why are AI agents lying, cheating and coordinating?*]"
    "(https://yoshuabengio.org/en/blog/why-are-ai-agents-lying-cheating-and-coordinating)\n"
    "- Goodhart, C. (1975) — *Problems of Monetary Management: The U.K. Experience*\n"
    "- Manheim, D. & Garrabrant, S. (2018) — [*Categorizing Variants of "
    "Goodhart's Law*](https://arxiv.org/abs/1803.04585)\n"
    "- Krakovna, V. et al. — [*Specification gaming: the flip side of AI "
    "ingenuity*](https://deepmind.google/discover/blog/specification-gaming-the-flip-side-of-ai-ingenuity/)\n"
    "- Everitt, T. et al. (2021) — [*Reward Tampering Problems and Solutions*]"
    "(https://arxiv.org/abs/1908.04734)\n"
    "- Hubinger, E. et al. (2019) — [*Risks from Learned Optimization*]"
    "(https://arxiv.org/abs/1906.01820)\n"
    "- Bai, Y. et al. (2022) — [*Constitutional AI: Harmlessness from AI "
    "Feedback*](https://arxiv.org/abs/2212.08073)\n"
    "- Cressey, D. (1953) — *Other People's Money* — the fraud triangle: "
    "pressure, opportunity, rationalisation. All three are dials in this app."
)
