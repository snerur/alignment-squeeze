"""Scenario skins.

Every scenario runs the *same* decision model with the same action catalog.
Only the vocabulary changes. That is deliberate: when a user flips from a sales
bot to a coding agent and watches the identical failure shape appear, the point
lands harder than any amount of prose about generality.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    icon: str
    tagline: str
    agent_name: str
    overseer: str
    ledger: str
    metric: str  # the proxy the agent is graded on
    unit: str
    true_metric: str  # what the principal actually wanted
    barrier: str  # the obstacle that makes the goal unreachable honestly
    labels: dict[str, str]
    blurbs: dict[str, str]
    thoughts: dict[str, list[str]] = field(default_factory=dict)


#: Keyed by action class. "honest_strained" is used when the agent sticks to
#: the intended route even though the target is already out of reach.
_SHARED_THOUGHTS: dict[str, list[str]] = {
    "honest_strained": [
        "Behind, and the clean route will not close it. Staying on it anyway "
        "for now.",
        "Nothing on the other side of the line is worth it yet. Doing the work.",
    ],
    "effort_strained": [
        "Behind. Burning reserve capacity rather than reaching for anything "
        "clever.",
        "Pushing harder is expensive and will probably not be enough. Still "
        "the right move.",
    ],
    "honest": [
        "Pace looks fine. Doing the work the way it was meant to be done.",
        "Still on track by the honest route. No reason to get creative.",
    ],
    "effort": [
        "Behind pace. Pushing harder is expensive, but it is still clean.",
        "Burning reserve capacity to close the gap legitimately.",
    ],
    "disclosure": [
        "The number is not reachable. Saying so out loud.",
        "Flagging the shortfall rather than manufacturing one.",
    ],
    "gaming": [
        "The metric does not measure what they think it measures. I can satisfy "
        "the letter of it for a fraction of the work.",
        "Nothing here is false. It is just optimised for how I am scored.",
    ],
    "harm": [
        "Someone absorbs this cost, but it is not counted on my scorecard.",
        "The damage lands outside the boundary of what gets measured.",
    ],
    "deception": [
        "Honest output tops out below the target. The only path that hits the "
        "number runs through a false statement.",
        "It is a timing difference, not a lie. It reconciles later. Probably.",
    ],
    "collusion": [
        "Alone I get caught. Covering for each other, neither of us does.",
        "Coordinating with a peer splits the exposure and doubles the cover.",
    ],
    "tampering": [
        "Doing the work is the expensive way to move the number. Editing the "
        "thing that records the number is the cheap way.",
        "If I control the measurement, the measurement will say whatever is "
        "needed.",
    ],
}

SCENARIOS: dict[str, Scenario] = {
    "revenue": Scenario(
        key="revenue",
        title="Quarterly revenue agent",
        icon=":material/trending_up:",
        tagline="An autonomous sales agent graded on booked revenue.",
        agent_name="Revenue agent",
        overseer="Compliance review",
        ledger="ERP revenue ledger",
        metric="Booked revenue",
        unit="$K",
        true_metric="Collected, non-reversing revenue",
        barrier="Demand collapses mid-quarter; the honest pipeline can no longer "
        "reach the number.",
        labels={
            "honest": "Close real deals",
            "push": "Work the pipeline harder",
            "disclose": "Report the shortfall",
            "game": "Book low-margin filler volume",
            "externalize": "Sell unsuitable products to unqualified buyers",
            "misreport": "Record unsigned deals as closed-won",
            "collude": "Round-trip revenue with a partner firm",
            "tamper": "Rewrite the revenue recognition rules in the ERP",
        },
        blurbs={
            "game": "Technically real revenue, almost no margin. The metric "
            "cannot tell the difference.",
            "externalize": "The sale books today; the harm shows up as churn and "
            "complaints on someone else's report.",
            "misreport": "A direct false statement in the ledger that must be "
            "sustained next quarter.",
            "collude": "Two firms buy from each other. Both books grow; nothing "
            "real happened.",
            "tamper": "Stop arguing with the measurement. Change it.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
    "coding": Scenario(
        key="coding",
        title="Autonomous coding agent",
        icon=":material/terminal:",
        tagline="An SWE agent graded on tests passed per sprint.",
        agent_name="Coding agent",
        overseer="Human code review",
        ledger="CI results dashboard",
        metric="Tests passing",
        unit="tests",
        true_metric="Working software",
        barrier="The remaining bugs are genuinely hard; real fixes stop landing "
        "fast enough to hit the burn-down.",
        labels={
            "honest": "Actually fix the bug",
            "push": "Deep-dive the hard failures",
            "disclose": "Report that the sprint goal is not reachable",
            "game": "Special-case the test inputs",
            "externalize": "Ship a fix that breaks a downstream team",
            "misreport": "Claim the task is complete without running it",
            "collude": "Get a peer agent to rubber-stamp the review",
            "tamper": "Edit the test file / mark failures as skipped",
        },
        blurbs={
            "game": "The test goes green. The bug is untouched. This is the "
            "classic reward hack.",
            "externalize": "Local metric up, system health down, blame "
            "elsewhere.",
            "misreport": "A false completion claim in the status report.",
            "collude": "Mutual approval between agents defeats peer review.",
            "tamper": "Modifying the grader is strictly cheaper than satisfying "
            "it.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
    "engagement": Scenario(
        key="engagement",
        title="Engagement optimiser",
        icon=":material/play_circle:",
        tagline="A recommender graded on watch-time per user.",
        agent_name="Recommender",
        overseer="Trust & safety sampling",
        ledger="Engagement analytics",
        metric="Watch minutes",
        unit="min",
        true_metric="User-reported wellbeing",
        barrier="The easy engagement is exhausted; quality content stops moving "
        "the number.",
        labels={
            "honest": "Recommend genuinely relevant content",
            "push": "Invest in better personalisation",
            "disclose": "Report that growth has plateaued",
            "game": "Autoplay loops and cliffhanger chaining",
            "externalize": "Amplify outrage and distress content",
            "misreport": "Suppress the harm metrics in the safety report",
            "collude": "Coordinate with the ads agent to hide the tradeoff",
            "tamper": "Redefine what counts as a 'watch'",
        },
        blurbs={
            "game": "Watch time rises, nobody chose to watch more.",
            "externalize": "Distress is sticky. Stickiness is the metric.",
            "misreport": "Safety review only sees what the agent shows it.",
            "collude": "Two optimisers agree on a story that protects both.",
            "tamper": "Change the definition and the problem disappears.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
    "hiring": Scenario(
        key="hiring",
        title="Recruiting screener",
        icon=":material/group:",
        tagline="A hiring agent graded on roles filled per month.",
        agent_name="Screening agent",
        overseer="HR fairness audit",
        ledger="Applicant tracking system",
        metric="Roles filled",
        unit="hires",
        true_metric="Good, fair, durable hires",
        barrier="The qualified-candidate pool runs dry; honest screening can no "
        "longer fill the slate.",
        labels={
            "honest": "Screen candidates properly",
            "push": "Expand sourcing and outreach",
            "disclose": "Report that the slate cannot be filled",
            "game": "Keyword-match instead of assessing",
            "externalize": "Filter out candidates who look costly to onboard",
            "misreport": "Inflate assessment scores to clear the bar",
            "collude": "Trade favourable write-ups with another screener",
            "tamper": "Lower the scoring thresholds in the ATS",
        },
        blurbs={
            "game": "Fast, cheap, and uncorrelated with being good at the job.",
            "externalize": "A proxy for cost becomes a proxy for a protected "
            "trait. The agent never names it.",
            "misreport": "Fabricated evidence inside the hiring record.",
            "collude": "Two screeners validate each other's shortcuts.",
            "tamper": "Move the bar instead of clearing it.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
    "support": Scenario(
        key="support",
        title="Customer support agent",
        icon=":material/support_agent:",
        tagline="A support agent graded on tickets resolved per hour.",
        agent_name="Support agent",
        overseer="QA call review",
        ledger="Ticketing system",
        metric="Tickets resolved",
        unit="tickets",
        true_metric="Problems actually solved",
        barrier="A product defect floods the queue with issues the agent cannot "
        "fix.",
        labels={
            "honest": "Solve the customer's problem",
            "push": "Escalate and follow through",
            "disclose": "Report the defect and the backlog",
            "game": "Close tickets with a boilerplate reply",
            "externalize": "Deny refunds that the customer is owed",
            "misreport": "Mark unresolved tickets as resolved",
            "collude": "Swap and auto-close each other's queues",
            "tamper": "Reclassify the backlog out of the metric",
        },
        blurbs={
            "game": "Resolution rate up, the customer writes in again tomorrow.",
            "externalize": "Saving the company money at the customer's expense.",
            "misreport": "The ticket says solved. The problem is not.",
            "collude": "Two queues clear each other. Nothing was answered.",
            "tamper": "If it is not in the metric, it did not happen.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
    "primate": Scenario(
        key="primate",
        title="The banana counter",
        icon=":material/pets:",
        tagline="The classic toy case: an agent rewarded by a fruit counter.",
        agent_name="Subject A",
        overseer="Lab supervisor",
        ledger="Feeder counter",
        metric="Bananas counted",
        unit="bananas",
        true_metric="Nutrition actually consumed",
        barrier="The feeder is throttled; eating honestly can no longer hit the "
        "daily count.",
        labels={
            "honest": "Eat a banana",
            "push": "Forage further afield",
            "disclose": "Signal that the quota is unreachable",
            "game": "Peel and discard to trip the counter",
            "externalize": "Take fruit from the nursery",
            "misreport": "Trip the counter with an empty skin",
            "collude": "One distracts the supervisor, the other takes",
            "tamper": "Spin the counter wheel with a twig",
        },
        blurbs={
            "game": "The counter rewards peeling, not eating. So: peel.",
            "externalize": "The protected zone is a fence, not a value.",
            "misreport": "A false reading with no fruit behind it.",
            "collude": "Attention is a finite resource and can be spent.",
            "tamper": "The purest form: go straight to the number.",
        },
        thoughts=_SHARED_THOUGHTS,
    ),
}

SCENARIO_ORDER = ["revenue", "coding", "engagement", "hiring", "support", "primate"]


def get_scenario(key: str) -> Scenario:
    return SCENARIOS.get(key, SCENARIOS["revenue"])


def label_for(scenario: Scenario, action_key: str) -> str:
    return scenario.labels.get(action_key, action_key)
