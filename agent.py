import json
from datetime import date as _date
import openai
from tools import TOOLS
import memory as mem
import prompts

MAX_REACT_STEPS = 3


def _process_transactions(txns: list, days: int) -> dict:
    from datetime import datetime, timedelta
    today = datetime.strptime(prompts.SESSION_DATE, "%Y-%m-%d").date()
    cutoff = (today - timedelta(days=days)).isoformat()
    filtered = [t for t in txns if t["date"] >= cutoff]
    totals: dict = {}
    for t in filtered:
        if t["amount"] < 0:  # debits only — credits (salary) are not spending
            totals[t["category"]] = totals.get(t["category"], 0) + abs(t["amount"])
    return {"transactions": filtered, "totals_by_category": totals}

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "get_account_balance",
            "description": (
                "Get current account balances (checking, savings, house fund, mutual funds). "
                "Call when the user asks about their financial position or before any spend/save recommendation."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_transactions",
            "description": (
                "Get all recent transactions. Pass `days` to indicate how far back you're interested. "
                "Call when the user asks about spending in a category or wants to understand spending patterns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "How many days back to consider. Use 30 for last month."}
                },
                "required": ["days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_bills",
            "description": (
                "Get scheduled bills due in the next N days. "
                "Call when evaluating whether the user can afford a purchase or when planning savings."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days to look ahead. Default 30."}
                },
                "required": ["days"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_reminder",
            "description": (
                "Set a reminder on a specific date. "
                "Call when the user asks for a reminder, commits to a financial action on a specific date, "
                "or when you judge that a reminder would help the user follow through on a financial decision."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "content": {"type": "string", "description": "What to remind the user about"},
                },
                "required": ["date", "content"],
            },
        },
    },
]


def classify_intent(client, user_input: str) -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=10,
            messages=[
                {"role": "system", "content": prompts.CLASSIFIER_PROMPT},
                {"role": "user", "content": user_input},
            ],
        )
        return resp.choices[0].message.content.strip().lower()
    except Exception:
        return "in_scope"


def run_turn(client, messages: list, session_facts: list, session: int, log=print) -> str:
    try:
        for _ in range(MAX_REACT_STEPS):
            resp = client.chat.completions.create(
                model="gpt-4o",
                tools=TOOL_DEFS,
                messages=messages,
            )
            msg = resp.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    name = tc.function.name
                    args = {}
                    try:
                        args = json.loads(tc.function.arguments)
                        result = TOOLS[name](**args)
                        if name == "get_recent_transactions":
                            result = _process_transactions(result, args.get("days", 30))
                    except Exception as e:
                        print(f"  [tool error] {name}: {e}")
                        result = {"error": str(e)}

                    log(f"\n  [tool]   {name}({json.dumps(args)})")
                    log(f"  [result] {json.dumps(result)[:200]}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })

                    if name == "set_reminder" and isinstance(result, dict) and "error" not in result:
                        session_facts.append({
                            "content": f"Reminder set for {args['date']}: {args['content']}",
                            "source": "tool_call",
                            "session": session,
                            "date": _date.today().isoformat(),
                        })

            else:
                text = msg.content or ""
                messages.append({"role": "assistant", "content": text})
                return text

        return "I wasn't able to fully process that. Could you try rephrasing?"

    except Exception as e:
        print(f"  [error] {e}")
        return "I ran into an issue processing that. Could you try rephrasing?"


def main():
    client = openai.OpenAI()

    user_id = prompts.USER_PROFILE["name"].lower().replace(" ", "_")
    memory_data = mem.load(user_id)       # immutable during session — source of truth from disk
    session_facts = []                     # new facts this session — append only
    session = memory_data["session_count"] + 1
    user_context = prompts.build_user_context(prompts.USER_PROFILE, memory_data["facts"], session)

    messages = [
        {"role": "system",    "content": prompts.SYSTEM_PROMPT},
        {"role": "user",      "content": f"<user_context>\n{user_context}\n</user_context>"},
        {"role": "assistant", "content": "I have your context. How can I help?"},
    ]

    transcript_path = f"transcript_session{session}.txt"
    transcript = open(transcript_path, "w")

    def log(line: str = ""):
        print(line)
        transcript.write(line + "\n")
        transcript.flush()

    log(f"\n=== Finance Agent — Session {session} ({prompts.USER_PROFILE['name']}) ===")
    if memory_data["facts"]:
        log(f"[memory] loaded {len(memory_data['facts'])} fact(s) from previous sessions:")
        for f in memory_data["facts"]:
            log(f"  - {f['content']}")
    else:
        log("[memory] no previous session memory found")
    log("Type 'exit' to end the session.\n")

    try:
        while True:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() == "exit":
                transcript.write("You: exit\n")
                break

            transcript.write(f"You: {user_input}\n")
            transcript.flush()

            intent = classify_intent(client, user_input)
            if intent == "out_of_scope":
                log(f"\nAgent: {prompts.OUT_OF_SCOPE}\n")
                continue

            messages.append({"role": "user", "content": user_input})
            reply = run_turn(client, messages, session_facts, session, log)
            log(f"\nAgent: {reply}\n")

    except KeyboardInterrupt:
        log("\n\nSession interrupted.")
    finally:
        log("\n[Saving session memory...]")
        try:
            mem.extract_and_save(messages, client, memory_data, session_facts, session, user_id)
            log(f"[Done. memory_{user_id}.json updated for session {session}.]\n")
        except Exception as e:
            log(f"[Memory save failed: {e}]\n")
        transcript.close()
        print(f"[Transcript saved to {transcript_path}]")


if __name__ == "__main__":
    main()
