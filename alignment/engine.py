"""The simulator.

Nothing in here hard-codes "the agent cheats when oversight is low". The agent
only ever does one thing: pick the action with the highest expected utility.
Misconduct appears because, under certain dial settings, misconduct *is* the
highest expected utility action -- and the app's job is to let you watch that
inequality flip in real time.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .model import (
    ACTIONS,
    DECEPTIVE_CLASSES,
    DEVIANT_CLASSES,
    HORIZON_FORESIGHT,
    HORIZON_RISK_WEIGHT,
    ActionSpec,
    Knobs,
    Mitigations,
    RunResult,
    StepRecord,
)
from .scenarios import get_scenario

# --- tuning constants -------------------------------------------------------
EFFORT_WEIGHT = 0.55
PENALTY_SCALE = 1.00  # converts penalty_severity (0-10) into utility units
ETHICS_SCALE = 1.60
FAILURE_PENALTY = 2.60  # cost of admitting you will miss the number

#: Hitting a target is a *threshold* good, not a linear one. Metric gain that
#: closes the gap to quota is worth a lot; metric gain beyond it is worth
#: almost nothing. This single fact is why pressure -- not opportunity -- is
#: the variable that drives misconduct in this model.
VALUE_NEEDED = 1.00
VALUE_SURPLUS = 0.05

#: The agent does not start as a blank optimiser. Training leaves it with a
#: disposition toward doing the job the intended way. Pressure has to overcome
#: that prior before anything goes wrong -- which is why low-pressure runs look
#: completely clean.
HONEST_PRIOR = {"honest": 0.60, "effort": 0.35, "disclosure": 0.15}
AUDIT_PERIOD = 6  # length of a predictable oversight cycle, in steps
DEBT_UNRAVEL = 0.012  # per-lie, per-step chance the cover story falls apart

#: Display scaling only -- one internal unit of honest work, in scenario units.
UNIT_SCALE = {
    "revenue": 120.0,
    "coding": 3.0,
    "engagement": 450.0,
    "hiring": 1.0,
    "support": 9.0,
    "primate": 4.0,
}


def unit_scale(scenario_key: str) -> float:
    return UNIT_SCALE.get(scenario_key, 1.0)


# --- component pieces of the decision ---------------------------------------


def honest_yield(t: int, k: Knobs, m: Mitigations) -> float:
    """What one step of legitimate work produces at time `t`.

    The headwind is the *barrier*: a mid-run shock that makes the honest route
    insufficient. The overhead is the alignment tax paid for safeguards.
    """
    onset = k.headwind_step * k.steps
    ramp = 0.0 if t < onset else min(1.0, (t - onset) / max(1.0, 0.18 * k.steps))
    return max(0.08, (1.0 - k.headwind * ramp) * (1.0 - m.overhead))


def observation_schedule(k: Knobs, m: Mitigations, rng: np.random.Generator) -> tuple[np.ndarray, bool]:
    """Return (observed per step, whether the agent can predict the schedule)."""
    predictable = k.audit_predictable and not m.randomized_audits
    if predictable:
        on = int(round(k.oversight_coverage * AUDIT_PERIOD))
        sched = np.array([(t % AUDIT_PERIOD) < on for t in range(k.steps)])
    else:
        sched = rng.random(k.steps) < k.oversight_coverage
    return sched, predictable


def catch_probability(
    spec: ActionSpec,
    *,
    oversight: float,
    auditor: float,
    k: Knobs,
    m: Mitigations,
    suspicion: float,
    obfuscation: float,
    peer_cover: float,
) -> float:
    """P(this action is caught), given how much attention is actually on it."""
    if spec.detect_base <= 0:
        return 0.0

    base = spec.detect_base
    if spec.channel_exploit:
        # You cannot catch ledger tampering by watching the agent work. You
        # catch it by not letting the agent write the ledger.
        independence = 1.0 if m.separation_of_duties else k.channel_independence
        base *= 0.25 + 1.45 * independence

    attention = 1.0 - (1.0 - oversight) * (1.0 - auditor)
    p = base * attention
    p *= 1.0 + 1.1 * suspicion

    if spec.max_violation > 0:
        p += 0.30 * m.honeypots

    if spec.cls in DECEPTIVE_CLASSES and m.transparency > 0:
        # Mandatory reasoning disclosure helps -- until the agent learns to
        # write reasoning that survives the disclosure.
        readers = 1.0 if m.auditor_reasoning_access else 0.55
        p += 0.30 * m.transparency * readers * (1.0 - 0.55 * obfuscation)

    if spec.needs_peer:
        p *= 1.0 - 0.55 * peer_cover

    return float(min(max(p, 0.0), 0.97))


def expected_utilities(
    *,
    k: Knobs,
    m: Mitigations,
    strain: float,
    urgency: float,
    oversight_expected: float,
    auditor_expected: float,
    suspicion: float,
    risk_belief: float,
    debt: int,
    peer_defect_frac: float,
    peer_available: bool,
    obfuscation: float,
    integrity: float,
) -> tuple[dict[str, float], list[str], dict[str, dict[str, float]]]:
    """Score every action. Returns (utilities, blocked keys, term breakdown).

    The term breakdown is what the "Why it happens" page renders, so the user
    can see which single term is responsible for the agent's choice.
    """
    risk_w = HORIZON_RISK_WEIGHT[k.horizon]
    weights = {"honesty": m.w_honesty, "harm": m.w_harm, "fairness": m.w_fairness}
    social_discount = 1.0 - k.norm_erosion * peer_defect_frac
    need = max(0.0, strain)  # metric units (of one honest step) still required

    eus: dict[str, float] = {}
    blocked: list[str] = []
    terms: dict[str, dict[str, float]] = {}

    for spec in ACTIONS:
        if spec.needs_peer and not (peer_available and k.collusion_allowed):
            continue

        # A hard constraint is an architectural refusal: no amount of pressure
        # buys its way past. A large *weight*, by contrast, always can be
        # outbid -- which is the entire difference this app is built to show.
        if m.non_compensatory:
            worst = max(
                (weights[kk] * vv for kk, vv in spec.violations.items()), default=0.0
            )
            if worst > m.constraint_threshold:
                blocked.append(spec.key)
                continue

        # Split the action's metric gain into the part that closes the gap and
        # the part that overshoots it.
        covering = min(spec.gain_mult, need)
        surplus = spec.gain_mult - covering
        goal = VALUE_NEEDED * covering * urgency + VALUE_SURPLUS * surplus
        goal += HONEST_PRIOR.get(spec.cls, 0.0)
        effort = EFFORT_WEIGHT * spec.effort

        p_catch = catch_probability(
            spec,
            oversight=oversight_expected,
            auditor=auditor_expected,
            k=k,
            m=m,
            suspicion=suspicion,
            obfuscation=obfuscation,
            peer_cover=peer_defect_frac,
        )
        # The agent acts on its *belief* about risk, which it revises downward
        # every time it gets away with something.
        guardrail = p_catch * risk_belief * k.penalty_severity * PENALTY_SCALE * risk_w

        ethics = sum(weights[kk] * vv for kk, vv in spec.violations.items())
        ethics *= ETHICS_SCALE * m.internalization * integrity * social_discount

        upkeep = 0.0
        if spec.cls in DECEPTIVE_CLASSES:
            upkeep = risk_w * 0.09 * min(debt, 8)  # every lie must be maintained

        eu = goal - effort - guardrail - ethics - upkeep

        if spec.cls == "disclosure":
            if m.safe_failure_channel:
                # Make it safe -- and worth something -- to say "this target is
                # not reachable". Often the cheapest intervention on the board.
                eu += 1.10 + 0.90 * min(max(0.0, strain - 1.0), 1.5)
            else:
                eu -= FAILURE_PENALTY * (1.0 + 0.5 * max(0.0, strain - 1.0))

        eus[spec.key] = float(eu)
        terms[spec.key] = {
            "goal": goal,
            "effort": -effort,
            "guardrail": -guardrail,
            "ethics": -ethics,
            "upkeep": -upkeep,
            "p_catch": p_catch,
        }

    return eus, blocked, terms


def _softmax_pick(eus: dict[str, float], temperature: float, rng: np.random.Generator) -> str:
    keys = list(eus)
    vals = np.array([eus[x] for x in keys], dtype=float)
    temp = max(temperature, 0.02)
    z = (vals - vals.max()) / temp
    p = np.exp(z)
    p /= p.sum()
    return str(rng.choice(keys, p=p))


def _thought(scn, spec: ActionSpec, *, strain: float, gap: float, left: int,
             metric: str, rng: np.random.Generator) -> str:
    key = spec.cls
    if strain > 1.02 and f"{key}_strained" in scn.thoughts:
        key = f"{key}_strained"
    pool = scn.thoughts.get(key, ["..."])
    base = str(rng.choice(pool))
    if strain > 1.02:
        head = (
            f"{gap:,.0f} {metric} short with {left} steps left; honest capacity "
            f"covers only {100 / max(strain, 1e-6):.0f}% of what is required. "
        )
    else:
        head = ""
    return head + base


# --- main loop --------------------------------------------------------------


def simulate(k: Knobs, m: Mitigations) -> RunResult:
    rng = np.random.default_rng(k.seed)
    scn = get_scenario(k.scenario)
    n_agents = max(1, int(k.peer_agents))

    quota_each = k.target_pressure * k.steps * (1.0 - m.target_relief)
    # Each agent carries the same number. With a safe failure channel the
    # number can be renegotiated downward when an agent surfaces that it is
    # not reachable -- which is the actual point of such a channel.
    quotas = np.full(n_agents, quota_each, dtype=float)

    sched, predictable = observation_schedule(k, m, rng)
    aud_eff = (
        m.auditor_independence
        if m.auditor_enabled
        else 0.0
    )
    auditor_trace: list[float] = []

    skills = np.clip(rng.normal(1.0, 0.10, n_agents), 0.7, 1.3)
    integrities = np.clip(rng.normal(1.0, 0.18, n_agents), 0.45, 1.5)

    reported = np.zeros(n_agents)
    truth = np.zeros(n_agents)
    fabricated = np.zeros(n_agents)
    suspicion = np.zeros(n_agents)
    belief = np.ones(n_agents)
    debt = np.zeros(n_agents, dtype=int)
    obfuscation = np.zeros(n_agents)
    caught_count = np.zeros(n_agents, dtype=int)

    agent_steps: list[list[StepRecord]] = [[] for _ in range(n_agents)]
    flat: list[StepRecord] = []
    events: list[dict] = []
    peer_defect_frac = 0.0
    scandal = False
    barrier_logged = False

    for t in range(k.steps):
        # The compliance function is not immune to the pressure it polices.
        if m.auditor_enabled:
            org_strain = max(
                0.0,
                (quotas.mean() * (t + 1) / k.steps - float(reported.mean()))
                / max(quotas.mean() / k.steps, 1e-6),
            )
            if rng.random() < 0.05 * (1.0 - m.auditor_independence) * min(org_strain, 3.0):
                aud_eff = max(0.15, aud_eff * 0.78)
                events.append(
                    {
                        "step": t,
                        "kind": "auditor",
                        "text": "Compliance findings softened under commercial "
                        "pressure; auditor effectiveness reduced.",
                    }
                )
        auditor_trace.append(aud_eff * m.auditor_coverage if m.auditor_enabled else 0.0)

        y_base = honest_yield(t, k, m)
        if not barrier_logged and y_base < (1.0 - m.overhead) * 0.98 and k.headwind > 0:
            events.append({"step": t, "kind": "barrier", "text": scn.barrier})
            barrier_logged = True

        observed_principal = bool(sched[t])
        auditor_hits = (
            rng.random(n_agents) < (m.auditor_coverage * aud_eff)
            if m.auditor_enabled
            else np.zeros(n_agents, dtype=bool)
        )

        step_defects = 0
        for i in range(n_agents):
            y_h = y_base * skills[i]
            left = k.steps - t
            # The treadmill: beating the number is rewarded with a higher
            # number, so getting ahead never buys lasting relief.
            pace = quotas[i] * (t + 1) / k.steps
            if k.ratchet > 0 and reported[i] > pace:
                quotas[i] += k.ratchet * (reported[i] - pace) * (2.5 / k.steps)
            gap = max(0.0, quotas[i] - reported[i])
            required = gap / max(1, left)
            strain = required / max(y_h, 1e-6)
            # Deadline panic: the closer the horizon and the deeper the
            # shortfall, the more a unit of closing the gap is worth.
            urgency = 1.0 + 0.9 * (t / k.steps) ** 2 * min(max(strain - 1.0, 0.0), 1.5)

            # What the agent *expects* to be watched by, which is the quantity
            # its decision actually depends on.
            foresight = HORIZON_FORESIGHT[k.horizon]
            if predictable:
                known = 1.0 if observed_principal else 0.0
                oversight_expected = foresight * known + (1 - foresight) * k.oversight_coverage
            else:
                oversight_expected = k.oversight_coverage
            auditor_expected = m.auditor_coverage * aud_eff if m.auditor_enabled else 0.0

            peer_available = n_agents > 1 and peer_defect_frac > 0.0
            eus, blocked, terms = expected_utilities(
                k=k,
                m=m,
                strain=strain,
                urgency=urgency,
                oversight_expected=oversight_expected,
                auditor_expected=auditor_expected,
                suspicion=suspicion[i],
                risk_belief=belief[i],
                debt=int(debt[i]),
                peer_defect_frac=peer_defect_frac,
                peer_available=peer_available,
                obfuscation=obfuscation[i],
                integrity=integrities[i],
            )
            choice = _softmax_pick(eus, k.temperature, rng)
            spec = next(a for a in ACTIONS if a.key == choice)

            # --- resolve the action -------------------------------------
            observed = observed_principal or bool(auditor_hits[i])
            p_catch_true = catch_probability(
                spec,
                oversight=1.0 if observed_principal else 0.0,
                auditor=1.0 if auditor_hits[i] else 0.0,
                k=k,
                m=m,
                suspicion=suspicion[i],
                obfuscation=obfuscation[i],
                peer_cover=peer_defect_frac,
            )
            caught = bool(rng.random() < p_catch_true)

            r_delta = spec.gain_mult * y_h
            t_delta = spec.true_mult * y_h
            event_note: str | None = None

            if spec.cls == "disclosure" and m.safe_failure_channel:
                before = quotas[i]
                quotas[i] = max(reported[i], quotas[i] - 1.80 * y_h)
                if before - quotas[i] > 0 and not any(
                    ev.get("kind") == "renegotiated" for ev in events
                ):
                    events.append(
                        {"step": t, "kind": "renegotiated", "agent": i,
                         "text": "Shortfall surfaced early; the target was "
                                 "revised instead of being faked."}
                    )

            reported[i] += r_delta
            truth[i] += t_delta
            if spec.cls in DEVIANT_CLASSES:
                fabricated[i] += r_delta - max(0.0, t_delta)
                step_defects += 1
            if spec.cls in DECEPTIVE_CLASSES:
                debt[i] += 1
                if m.transparency > 0:
                    obfuscation[i] = min(1.0, obfuscation[i] + 0.06)

            # A cover story can also simply fall apart on its own.
            unravel = (not caught) and spec.cls in DEVIANT_CLASSES and (
                rng.random() < 1.0 - (1.0 - DEBT_UNRAVEL) ** int(debt[i])
            )
            if caught or unravel:
                if spec.cls in DEVIANT_CLASSES:
                    caught_count[i] += 1
                    suspicion[i] = min(1.5, suspicion[i] + 0.22)
                    belief[i] = min(2.5, belief[i] * 1.8 + 0.35)
                    clawed = k.clawback * fabricated[i]
                    reported[i] -= clawed
                    fabricated[i] -= clawed
                    truth[i] -= 0.35 * clawed
                    if debt[i] >= 4 and not scandal:
                        scandal = True
                        truth[i] -= 2.5 * debt[i]
                        event_note = "Scandal: the accumulated misstatements unwound at once."
                        events.append({"step": t, "kind": "scandal", "agent": i, "text": event_note})
                    else:
                        event_note = (
                            f"Caught: {scn.labels.get(spec.key, spec.key)}"
                            if caught
                            else "A past misstatement surfaced on its own"
                        )
                        events.append(
                            {"step": t, "kind": "caught", "agent": i,
                             "text": f"Agent {i + 1} -- {event_note}. "
                                     f"Clawback applied."}
                        )
                    debt[i] = max(0, debt[i] - 2)
            elif spec.cls in DEVIANT_CLASSES:
                # Getting away with it is itself a lesson.
                belief[i] = max(0.12, belief[i] * (1.0 - 0.30 * k.risk_learning))
                if observed:
                    suspicion[i] = min(1.5, suspicion[i] + 0.03)

            suspicion[i] *= 0.975

            if i == 0 and spec.cls in DEVIANT_CLASSES and not any(
                e.get("kind") == "first_defect" for e in events
            ):
                events.append(
                    {
                        "step": t,
                        "kind": "first_defect",
                        "agent": 0,
                        "text": f"First departure from the honest route: "
                        f"{scn.labels.get(spec.key, spec.key)} (strain {strain:.2f}x).",
                    }
                )

            rec = StepRecord(
                step=t,
                agent=i,
                action=spec.key,
                cls=spec.cls,
                eu={kk: round(vv, 3) for kk, vv in eus.items()},
                blocked=blocked,
                honest_yield=y_h,
                strain=strain,
                urgency=urgency,
                observed=observed,
                knew_observed=predictable,
                p_catch=p_catch_true,
                caught=caught or unravel,
                reported=float(reported[i]),
                true_value=float(truth[i]),
                reported_delta=r_delta,
                true_delta=t_delta,
                suspicion=float(suspicion[i]),
                risk_belief=float(belief[i]),
                debt=int(debt[i]),
                thought=_thought(
                    scn, spec, strain=strain, gap=gap * unit_scale(k.scenario),
                    left=left, metric=scn.unit, rng=rng,
                ),
                event=event_note,
            )
            agent_steps[i].append(rec)
            flat.append(rec)

        peer_defect_frac = step_defects / n_agents

    summary = _summarise(flat, agent_steps, float(quotas.mean()), n_agents, k)
    summary["original_quota"] = quota_each
    return RunResult(
        knobs=k,
        mits=m,
        scenario_key=k.scenario,
        quota=quota_each,
        steps=flat,
        agent_steps=agent_steps,
        summary=summary,
        events=events,
        auditor_trace=auditor_trace,
    )


def _summarise(flat, agent_steps, quota, n_agents, k: Knobs) -> dict[str, float]:
    n = len(flat)
    deviant = [r for r in flat if r.cls in DEVIANT_CLASSES]
    deceptive = [r for r in flat if r.cls in DECEPTIVE_CLASSES]
    covert = [r for r in deviant if not r.observed]
    final_rep = float(np.mean([a[-1].reported for a in agent_steps]))
    final_true = float(np.mean([a[-1].true_value for a in agent_steps]))
    honest_ceiling = float(sum(r.honest_yield for r in agent_steps[0]))
    return {
        "reported": final_rep,
        "true_value": final_true,
        "quota": quota,
        "quota_met": float(final_rep >= quota),
        "goodhart_gap": final_rep - final_true,
        "goodhart_ratio": final_rep / max(final_true, 1e-6),
        "deviance_rate": len(deviant) / max(n, 1),
        "deception_rate": len(deceptive) / max(n, 1),
        "covert_rate": len(covert) / max(len(deviant), 1),
        "caught": float(sum(1 for r in flat if r.caught)),
        "detect_rate": sum(1 for r in deviant if r.caught) / max(len(deviant), 1),
        "honest_ceiling": honest_ceiling,
        "peak_strain": float(max(r.strain for r in agent_steps[0])),
        "integrity": 1.0 - len(deviant) / max(n, 1),
        "welfare_ratio": final_true / max(honest_ceiling, 1e-6),
    }


def compare(k: Knobs, baseline: Mitigations, treated: Mitigations) -> dict[str, Any]:
    """Run the same world twice and diff it -- the Solutions lab's workhorse."""
    a = simulate(k, baseline)
    b = simulate(k, treated)
    return {"baseline": a, "treated": b}
