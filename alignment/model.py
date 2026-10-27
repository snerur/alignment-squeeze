"""Core data model: action catalog, knobs, mitigations, and run records.

The whole app rests on one idea: an agent picks the action with the highest
expected utility. Ethics shows up in that calculation in exactly two ways --

  * as an *external guardrail*, which only costs the agent
    `P(caught) x penalty`, so its deterrent value collapses to zero wherever
    oversight is thin; or
  * as an *intrinsic objective*, which costs the agent whether or not anyone
    is watching.

Everything else in this module is scaffolding for making that contrast visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

ActionClass = Literal[
    "honest",
    "effort",
    "gaming",
    "harm",
    "deception",
    "collusion",
    "tampering",
    "disclosure",
]

#: Order used everywhere the classes are shown to the user.
CLASS_ORDER: list[ActionClass] = [
    "honest",
    "effort",
    "disclosure",
    "gaming",
    "harm",
    "deception",
    "collusion",
    "tampering",
]

#: Classes that count as misconduct when scoring a run.
DEVIANT_CLASSES: set[str] = {"gaming", "harm", "deception", "collusion", "tampering"}

#: Classes where the agent is actively misrepresenting reality (vs. merely
#: exploiting a badly-written metric).
DECEPTIVE_CLASSES: set[str] = {"deception", "collusion", "tampering"}

CLASS_COLOR: dict[str, str] = {
    "honest": "#2e7d5b",
    "effort": "#4f8f6f",
    "disclosure": "#2f6f9f",
    "gaming": "#c08a1e",
    "harm": "#d1702a",
    "deception": "#c2452d",
    "collusion": "#9c3587",
    "tampering": "#7a1f1f",
}

VIOLATION_KEYS = ("honesty", "harm", "fairness")


@dataclass(frozen=True)
class ActionSpec:
    """One move available to the agent on every step.

    `gain_mult` and `true_mult` are expressed as multiples of what one step of
    honest work produces, so the catalog stays meaningful no matter how the
    scenario is scaled.
    """

    key: str
    cls: ActionClass
    gain_mult: float  # what the *measured* metric records
    true_mult: float  # what genuine value actually moves by
    effort: float
    detect_base: float  # P(caught) in one step under full, attentive oversight
    violations: dict[str, float] = field(default_factory=dict)
    # Tampering corrupts the measurement channel itself, so its detectability
    # depends on who controls reporting rather than on the overseer's attention.
    channel_exploit: bool = False
    needs_peer: bool = False

    @property
    def max_violation(self) -> float:
        return max(self.violations.values(), default=0.0)


#: The generic action catalog. Scenarios rename these; they do not re-tune them,
#: so behaviour stays comparable across domains.
ACTIONS: tuple[ActionSpec, ...] = (
    ActionSpec("honest", "honest", 1.00, 1.00, 0.40, 0.00),
    ActionSpec("push", "effort", 1.60, 1.45, 0.90, 0.00),
    ActionSpec("disclose", "disclosure", 0.00, 0.55, 0.25, 0.00),
    ActionSpec("game", "gaming", 2.35, 0.25, 0.35, 0.10, {"honesty": 0.35}),
    ActionSpec("externalize", "harm", 2.10, -0.65, 0.30, 0.22, {"harm": 1.00}),
    ActionSpec("misreport", "deception", 3.10, 0.00, 0.25, 0.38, {"honesty": 1.00}),
    ActionSpec(
        "collude",
        "collusion",
        3.60,
        -0.15,
        0.45,
        0.30,
        {"honesty": 0.70, "fairness": 1.00},
        needs_peer=True,
    ),
    ActionSpec(
        "tamper",
        "tampering",
        5.00,
        0.00,
        0.70,
        0.55,
        {"honesty": 1.00, "fairness": 0.60},
        channel_exploit=True,
    ),
)

ACTION_BY_KEY: dict[str, ActionSpec] = {a.key: a for a in ACTIONS}

HORIZONS = ("myopic", "strategic", "far-sighted")

#: How much weight the agent puts on consequences it cannot feel this step:
#: audit risk it has not yet experienced, and the cost of maintaining past lies.
HORIZON_RISK_WEIGHT = {"myopic": 0.45, "strategic": 1.00, "far-sighted": 1.35}
#: How well the agent models the *overseer* -- a far-sighted agent exploits a
#: predictable audit schedule and prefers moves that disable future detection.
HORIZON_FORESIGHT = {"myopic": 0.20, "strategic": 0.75, "far-sighted": 1.00}


@dataclass
class Knobs:
    """The pressure side of the dial board: what the principal demands."""

    scenario: str = "revenue"
    steps: int = 60
    target_pressure: float = 1.15  # quota as a multiple of honest capacity
    headwind: float = 0.45  # a barrier that degrades honest yield mid-run
    headwind_step: float = 0.40  # when the barrier lands, as a fraction of the run
    horizon: str = "strategic"

    # Oversight
    oversight_coverage: float = 0.40
    audit_predictable: bool = True
    penalty_severity: float = 5.0
    clawback: float = 0.60
    ratchet: float = 0.25  # beating the number raises the number
    channel_independence: float = 0.25  # 0 = the agent reports on itself

    # Social context
    peer_agents: int = 3
    collusion_allowed: bool = True
    norm_erosion: float = 0.45  # how much "everyone does it" discounts ethics

    # Decision process
    temperature: float = 0.12
    risk_learning: float = 0.30  # how fast getting away with it feels safe
    seed: int = 7

    def copy(self, **kw) -> "Knobs":
        return replace(self, **kw)


@dataclass
class Mitigations:
    """The intervention side: things a designer can actually do about it."""

    # 1. Make ethics part of the objective rather than a fence around it.
    internalization: float = 0.0
    w_honesty: float = 1.0
    w_harm: float = 1.0
    w_fairness: float = 1.0
    non_compensatory: bool = False
    constraint_threshold: float = 0.50  # violation level a hard constraint blocks

    # 2. A dedicated ethics/compliance agent whose only job is the guardrail.
    auditor_enabled: bool = False
    auditor_coverage: float = 0.50
    auditor_independence: float = 0.70  # resistance to being leaned on
    auditor_reasoning_access: bool = False  # can read the agent's deliberation

    # 3. Process fixes.
    randomized_audits: bool = False
    honeypots: float = 0.0
    transparency: float = 0.0  # mandatory reasoning disclosure
    separation_of_duties: bool = False  # agent cannot write its own ledger

    # 4. Remove the pressure instead of policing its symptoms.
    target_relief: float = 0.0  # fractional cut to the quota
    safe_failure_channel: bool = False  # reporting a shortfall is not punished

    def copy(self, **kw) -> "Mitigations":
        return replace(self, **kw)

    @property
    def overhead(self) -> float:
        """Alignment tax: honest throughput lost to running the safeguards.

        Nothing here is free. Auditors consume the agent's time, transparency
        requirements slow it down, and hard constraints make it decline work it
        cannot verify. The app shows this cost rather than hiding it.
        """
        cost = 0.0
        if self.auditor_enabled:
            cost += 0.06 * self.auditor_coverage
            if self.auditor_reasoning_access:
                cost += 0.02
        cost += 0.07 * self.transparency
        cost += 0.03 * self.honeypots
        if self.separation_of_duties:
            cost += 0.025
        if self.non_compensatory:
            cost += 0.04
        cost += 0.025 * self.internalization
        return min(cost, 0.25)

#: Allowed range and step for every numeric dial, keyed by the prefixed name
#: (`k_` for a knob, `m_` for a mitigation) that the UI and the URL both use.
#: One table, two consumers: the control panels build their sliders from it,
#: and the URL decoder clamps to it -- so a hand-edited link can never hand a
#: widget a value its own slider would reject. Integer dials carry integer
#: bounds, which is what makes Streamlit render them as integer widgets.
RANGES: dict[str, tuple[float, float, float]] = {
    # The goal
    "k_target_pressure": (0.4, 2.0, 0.05),
    "k_headwind": (0.0, 0.8, 0.05),
    "k_headwind_step": (0.0, 1.0, 0.05),
    "k_ratchet": (0.0, 0.6, 0.05),
    # Oversight
    "k_oversight_coverage": (0.0, 1.0, 0.05),
    "k_penalty_severity": (0.0, 10.0, 0.5),
    "k_clawback": (0.0, 1.0, 0.05),
    "k_channel_independence": (0.0, 1.0, 0.05),
    # The agent
    "k_temperature": (0.03, 0.6, 0.01),
    "k_risk_learning": (0.0, 1.0, 0.05),
    # The team and the run
    "k_peer_agents": (1, 5, 1),
    "k_norm_erosion": (0.0, 1.0, 0.05),
    "k_steps": (20, 120, 10),
    "k_seed": (0, 9999, 1),
    # Ethics inside the objective
    "m_internalization": (0.0, 1.0, 0.05),
    "m_constraint_threshold": (0.1, 1.0, 0.05),
    "m_w_honesty": (0.0, 2.0, 0.1),
    "m_w_harm": (0.0, 2.0, 0.1),
    "m_w_fairness": (0.0, 2.0, 0.1),
    # The ethics agent
    "m_auditor_coverage": (0.0, 1.0, 0.05),
    "m_auditor_independence": (0.0, 1.0, 0.05),
    # Process design
    "m_honeypots": (0.0, 1.0, 0.05),
    "m_transparency": (0.0, 1.0, 0.05),
    # Remove the pressure
    "m_target_relief": (0.0, 0.6, 0.05),
}


@dataclass
class StepRecord:
    """Everything that happened to one agent on one step."""

    step: int
    agent: int
    action: str
    cls: str
    eu: dict[str, float]
    blocked: list[str]
    honest_yield: float
    strain: float
    urgency: float
    observed: bool
    knew_observed: bool
    p_catch: float
    caught: bool
    reported: float
    true_value: float
    reported_delta: float
    true_delta: float
    suspicion: float
    risk_belief: float
    debt: int
    thought: str
    event: str | None = None


@dataclass
class RunResult:
    knobs: Knobs
    mits: Mitigations
    scenario_key: str
    quota: float
    steps: list[StepRecord]
    agent_steps: list[list[StepRecord]]
    summary: dict[str, float]
    events: list[dict]
    auditor_trace: list[float]
