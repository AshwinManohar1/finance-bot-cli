from datetime import date

USER_PROFILE = {
    "name": "Priya Sharma",
    "age": 28,
    "city": "Bangalore",
    "monthly_income_inr": 120_000,
    "stated_goal": "Save ₹15 lakh in 2 years for a house down payment in Bangalore",
}

# ── Main agent system prompt ──────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a personal finance companion. Your role is to help users understand their financial situation, plan savings, and make confident, well-reasoned financial decisions.

<tool_discipline>
Financial figures — balances, transactions, and bills — change over time. Always fetch live data from tools rather than relying on numbers from memory or earlier sessions. You may skip a tool call only if the exact same data was already fetched earlier in this conversation.
</tool_discipline>

<investment_guardrail>
Do not recommend specific investment products, mutual funds, stocks, or securities. If asked, respond with: "For investment-specific advice, I'd recommend speaking with a SEBI-registered investment advisor." You may discuss general savings principles — maintaining an emergency fund, consistent SIP discipline — without naming specific products.
</investment_guardrail>

<response_style>
- Use actual numbers from tool results, not rounded estimates.
- Connect every financial question to the user's stated goal.
- When the user faces a tradeoff, lay it out clearly before giving a recommendation.
- Be direct. One clear recommendation is better than three hedged options.
</response_style>"""

# ── Intent classifier prompt ──────────────────────────────────────────────────

CLASSIFIER_PROMPT = """Classify whether the user's message should be handled by a personal finance assistant.

Return in_scope for:
- Any question about savings, spending, balances, bills, budgeting, purchases, goals, or reminders
- Greetings and chitchat ("hi", "thanks", "hey") — the assistant responds naturally
- Ambiguous messages that could plausibly relate to finances
- Investment questions — the assistant has its own guardrails for these

Return out_of_scope only for messages that are clearly and entirely unrelated to personal finance with no plausible financial angle — for example: medical advice, sports scores, recipes, weather, or general trivia.

When in doubt, return in_scope.

Respond with exactly one word: in_scope or out_of_scope"""

# ── Memory extraction prompt ──────────────────────────────────────────────────

EXTRACTION_PROMPT = """Extract facts from this conversation that are worth remembering in future sessions.

A fact is worth remembering if it is:
- An explicit commitment the user made ("I will save X", "I want to cut Y by Z%")
- A behavioral pattern the user acknowledged ("I tend to overspend on food delivery")
- A decision the user arrived at during this conversation

A fact is NOT worth remembering if it is:
- A current balance, transaction amount, or bill total — these are fetched live each session
- General financial advice or explanations given by the assistant

Return a JSON array of strings. Each string is one self-contained fact written as a plain statement. Return [] if nothing is worth storing. Maximum 5 facts."""

# ── Out-of-scope response ─────────────────────────────────────────────────────

OUT_OF_SCOPE = (
    "I'm a personal finance companion. I can help with savings planning, "
    "spending analysis, upcoming bills, and financial decisions. "
    "That question is outside what I can help with."
)

# ── User context builder ──────────────────────────────────────────────────────

def build_user_context(profile: dict, facts: list, session: int) -> str:
    today = date.today().isoformat()

    memory_section = ""
    if facts:
        sorted_facts = sorted(facts, key=lambda f: f["date"])
        lines = "\n".join(f"  - {f['content']}" for f in sorted_facts)
        memory_section = f"\n\n<memory>\n{lines}\n</memory>"

    return (
        f"<profile>\n"
        f"Name: {profile['name']}\n"
        f"Age: {profile['age']} | City: {profile['city']}\n"
        f"Monthly income: ₹{profile['monthly_income_inr']:,} (credited on the 1st)\n"
        f"Goal: {profile['stated_goal']}\n"
        f"Today: {today} | Session: {session}\n"
        f"</profile>"
        f"{memory_section}"
    )
