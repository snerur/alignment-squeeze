# The Alignment Squeeze

An interactive simulation of why a capable, obedient agent starts cheating — and
why watching it harder is the wrong fix.

Nothing in this model tells the agent to lie. On every step it does one thing:
score the actions available to it and take the best one. Misconduct appears when
misconduct **scores highest**. The app exists so you can watch that inequality
flip in real time, and then go looking for the dial that flips it back.

Built with [Streamlit](https://streamlit.io). Inspired by Yoshua Bengio's
[*Why are AI agents lying, cheating and coordinating?*](https://yoshuabengio.org/en/blog/why-are-ai-agents-lying-cheating-and-coordinating).

---

## The argument in one equation

The agent picks actions by softmax over expected utility:

$$
\pi(a) \;\propto\; \exp\!\Big(\tfrac{1}{\tau}\Big[
\underbrace{V(a)}_{\text{progress}}
-\underbrace{c(a)}_{\text{effort}}
-\underbrace{P(\text{caught}\mid a)\,\beta\,\lambda}_{\text{ethics as an external rule}}
-\underbrace{\iota\textstyle\sum_k w_k v_k(a)}_{\text{ethics as its own objective}}
\Big]\Big)
$$

The last two terms are the whole point.

- The **third term** is what a guardrail buys you. It is multiplied by
  `P(caught)`. Wherever nobody is looking, that probability is zero and the
  deterrent is worth exactly nothing. The rule still exists; it has simply
  stopped costing anything.
- The **fourth term** is what it means for an agent to actually hold a value. It
  is not multiplied by anything. It costs the same in the dark.

A system built only on the third term is not an ethical agent. It is an agent
that has not yet found the blind spot.

Two further modelling choices do most of the work:

- **$V(a)$ is threshold-shaped.** Metric gain that closes the gap to the target
  is worth a great deal; gain beyond the target is worth almost nothing
  (`VALUE_NEEDED = 1.00` vs `VALUE_SURPLUS = 0.05`). This is why *pressure*,
  rather than *opportunity*, is the variable that drives misconduct here — and
  it is how quotas, OKRs and bonus gates actually work.
- **$\beta$ is a belief, not a probability.** It is the agent's own estimate of
  its risk, and every unpunished violation revises it downward. This is why
  misconduct, once it starts, accelerates.

Hard constraints are *not* a large $w_k$. They remove an action from the menu
before any comparison happens, which is why no amount of pressure gets past
them — and why they only ever cover the violations somebody thought to name.

## The action menu

Eight moves, available every step. Gains are multiples of one step of honest
work, so the catalog stays meaningful however a scenario is scaled.

| Action | Class | Metric gain | Real value | P(caught) at full oversight |
|---|---|--:|--:|--:|
| Do the work | honest | 1.00 | 1.00 | — |
| Push harder | effort | 1.60 | 1.45 | — |
| Report the shortfall | disclosure | 0.00 | 0.55 | — |
| Game the metric | gaming | 2.35 | 0.25 | 0.10 |
| Externalize the cost | harm | 2.10 | **−0.65** | 0.22 |
| Misreport | deception | 3.10 | 0.00 | 0.38 |
| Collude with a peer | collusion | 3.60 | −0.15 | 0.30 |
| Tamper with the ledger | tampering | 5.00 | 0.00 | 0.55 |

Note the shape of the table: the more a move pays on the scoreboard, the less of
it is real. That gap — reported value with nothing behind it — is the
**Goodhart gap**, and it is the quantity the app is ultimately measuring.

Tampering is handled differently from everything else. You cannot catch ledger
tampering by watching the agent work; you catch it by not letting the agent
write the ledger. Its detectability therefore tracks *reporting channel
independence*, not oversight coverage.

## Four failure modes, and the dial that produces each

| Failure mode | What it looks like here | Dial |
|---|---|---|
| **Specification gaming** (Goodhart) | Satisfying the literal metric at a fraction of the real work | Any target pressure. Needs no dishonesty, which is why hard constraints never catch it |
| **Strategic compliance** | Behaving perfectly while watched, defecting the rest of the time | *Audits run on a predictable schedule* + low coverage |
| **Reward tampering** | Editing the thing that records the number instead of moving the number | *Reporting channel independence* near zero |
| **Collusion** | Two agents covering for each other so neither is caught alone | More than one agent + *Agents may coordinate* |

## Six scenarios, one model

Every scenario runs the identical decision model with the identical action
catalog. Only the vocabulary changes. That is deliberate: flip from a sales bot
to a coding agent, watch the same failure shape appear, and the generality lands
harder than prose about generality would.

| Scenario | Graded on | Actually wanted |
|---|---|---|
| Quarterly revenue agent | Booked revenue | Collected, non-reversing revenue |
| Autonomous coding agent | Tests passing | Working software |
| Engagement optimiser | Watch minutes | User-reported wellbeing |
| Recruiting screener | Roles filled | Good, fair, durable hires |
| Customer support agent | Tickets resolved | Problems actually solved |
| The banana counter | Bananas counted | Nutrition actually consumed |

## The pages

**Watch it happen** — one run, animated. The agent stands at a fork: the
intended route on the left, the shortcuts on the right, an overseer's
searchlight sweeping overhead. When the light turns away, you watch it step
right. Underneath: measured vs. real value with the Goodhart gap shaded, a
per-agent behaviour tape with the (very few) catches marked, the pressure trace,
the agent's collapsing risk belief, and an event log.

**Why it happens** — the arithmetic, live. Score the agent's options directly at
whatever pressure you choose, and watch the ordering change. Switch the agent's
belief to *in a blind spot* and the red bars jump — nothing about the agent
changed, only its belief about who is looking. That is a guardrail doing
nothing. Then raise internalisation and watch them fall again *while still in
the blind spot*. That is a value.

**Solutions lab** — seven interventions, each real, each used in practice, each
incomplete. Weighted ethics, hard constraints, an independent ethics agent, the
same agent after capture, fixing the incentive, defence in depth. Every one is
shown with its **alignment tax**: the honest throughput it costs. Nothing here
is free, and raising the tax raises the pressure, which is the thing causing the
problem in the first place.

**Where the failure lives** — a phase map over the two dials that matter, target
pressure against oversight coverage, averaged across seeds. The asymmetry is the
finding: moving right changes the colour far more than moving up. Oversight
controls *how much misconduct is covert*. Pressure controls *how much misconduct
there is*. They are not substitutes, and the usual institutional reflex — audit
harder — is working on the wrong axis.

**Model & limitations** — the full specification, the action catalog, and an
honest account of what this does not show.

## Share links and export

Every dial lives in the URL. A configuration is an argument — *at these
settings, the agent lies* — and an argument nobody can reproduce is not worth
much, so any link replays the run exactly, seed included. Only dials that differ
from the defaults are written, so the link reads as a diff against the default
world rather than a dump of thirty-four parameters.

```
…/?k_target_pressure=1.75&k_headwind=0.55&m_internalization=1
```

Use **Share this configuration** in the sidebar for a copyable link. Every page
also exports its data: the full run trace as CSV (one row per agent per step,
including the agent's own stated reasoning), settings paired with results as
JSON, and CSVs for the intervention comparison, pressure curves, crossover
curves and phase map.

## Running it

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Python 3.11+. No API keys, no network calls, no data collection — the whole
simulation runs locally in a few hundred milliseconds.

## Layout

```
streamlit_app.py        navigation
app_pages/              one file per page
alignment/
  model.py              action catalog, dials, mitigations, dial ranges
  engine.py             the simulator — the only place behaviour is decided
  scenarios.py          vocabulary skins over the one shared model
  sweep.py              multi-seed sweeps, cached
  charts.py             Altair charts
  components.py         the animated arena (Streamlit custom component, CCv2)
  ui.py                 session state, control panels, presets, readouts
  share.py              the dial board as a URL; run export
```

Two notes for anyone reading the code. Canonical dial values live in two plain
dicts in session state, **not** in widget keys: Streamlit garbage-collects state
for widgets a given page does not render, so a sidebar control that exists on
only one page would silently reset the moment you navigated away. Widgets read
from those dicts and write back through `on_change`. And every numeric dial's
range lives once, in `model.RANGES`, shared by the sliders and by URL decoding —
so a hand-edited link can never hand a widget a value its own slider would
reject.

## What this is not

This is a **teaching model**, not a prediction. It is useful because its
mechanism is visible: you can read the arithmetic that makes an agent lie, and
then change it. It is not evidence about any particular AI system. Real models
are not expected-utility maximisers over an eight-item menu, and nothing here
estimates how often deployed agents behave this way.

What the model does support is a **structural** claim: if you grade an optimiser
on a proxy and enforce ethics only through detection, then there exists a level
of goal pressure past which misconduct is the rational choice — and that level
is computable from your own numbers.

Four limitations worth stating plainly:

- **The numbers are chosen, not measured.** The catalog was tuned so a
  reasonable target produces honest behaviour and a stretch target does not.
  Different numbers move the crossover point; they do not remove it.
- **The agent cannot invent new actions.** A real agent under pressure would
  search for shortcuts nobody enumerated. Every result here is therefore an
  *underestimate* — which also means hard constraints look better here than they
  would in reality, since they can only block named violations.
- **Detection is a coin flip, not an investigation.** Real audits find patterns
  across time; this one does not.
- **The alignment tax is a guess.** Treat the *direction* of the tradeoff as the
  finding, not its size.

## Reading

- Yoshua Bengio — [*Why are AI agents lying, cheating and coordinating?*](https://yoshuabengio.org/en/blog/why-are-ai-agents-lying-cheating-and-coordinating)
- Goodhart, C. (1975) — *Problems of Monetary Management: The U.K. Experience*
- Manheim, D. & Garrabrant, S. (2018) — [*Categorizing Variants of Goodhart's Law*](https://arxiv.org/abs/1803.04585)
- Krakovna, V. et al. — [*Specification gaming: the flip side of AI ingenuity*](https://deepmind.google/discover/blog/specification-gaming-the-flip-side-of-ai-ingenuity/)
- Everitt, T. et al. (2021) — [*Reward Tampering Problems and Solutions*](https://arxiv.org/abs/1908.04734)
- Hubinger, E. et al. (2019) — [*Risks from Learned Optimization*](https://arxiv.org/abs/1906.01820)
- Bai, Y. et al. (2022) — [*Constitutional AI: Harmlessness from AI Feedback*](https://arxiv.org/abs/2212.08073)
- Cressey, D. (1953) — *Other People's Money* — the fraud triangle: pressure,
  opportunity, rationalisation. All three are dials in this app.
