"""Database of proven hook patterns that the hook writer pulls inspiration from."""

PROVEN_HOOKS: list[dict[str, str]] = [
    {
        "pattern": "The Contrarian Truth",
        "example": "Everyone tells you X. They're wrong. Here's what actually works.",
        "why_it_works": "Pattern interrupt + authority position; viewer needs the resolution.",
    },
    {
        "pattern": "The Specific Number",
        "example": "I made $47,832 in 11 days doing the opposite of what everyone teaches.",
        "why_it_works": "Specificity creates credibility; round numbers feel made up.",
    },
    {
        "pattern": "The Public Failure",
        "example": "I lost $200K because I believed the most common advice in my industry.",
        "why_it_works": "Vulnerability + stakes; cost-of-being-wrong is named upfront.",
    },
    {
        "pattern": "The Insider Reveal",
        "example": "There's a team running 20 AI agents to generate clients $10M in revenue.",
        "why_it_works": "Curiosity gap on the mechanism; viewer wants the how.",
    },
    {
        "pattern": "The Imminent Threat",
        "example": "If you're still doing X in 2026, you've already lost.",
        "why_it_works": "Time-bound urgency + identity threat; can't keep scrolling.",
    },
    {
        "pattern": "The Hidden Pattern",
        "example": "Every viral video I studied had the same 4 things. Nobody talks about #3.",
        "why_it_works": "Promised payoff at a specific point keeps attention to that point.",
    },
    {
        "pattern": "The Permission Slip",
        "example": "You don't need a big audience. You don't need a budget. You need this.",
        "why_it_works": "Removes objections before viewer can raise them.",
    },
    {
        "pattern": "The Unexpected Authority",
        "example": "A 19-year-old just outranked a Fortune 500 company on Google. Here's how.",
        "why_it_works": "Status inversion creates curiosity + relatability.",
    },
    {
        "pattern": "The Inside Joke",
        "example": "If you've ever stared at your screen wondering why nobody's watching — this is for you.",
        "why_it_works": "Specific in-group identification; viewer feels seen.",
    },
    {
        "pattern": "The Provocative Claim",
        "example": "Most 'gurus' on X have never built anything. Here's how to spot them in 30 seconds.",
        "why_it_works": "Tribal alignment + actionable promise; fight + payoff.",
    },
]


def as_inspiration_block() -> str:
    lines = []
    for h in PROVEN_HOOKS:
        lines.append(
            f"- {h['pattern']}\n  Example: {h['example']}\n  Why: {h['why_it_works']}"
        )
    return "\n".join(lines)
