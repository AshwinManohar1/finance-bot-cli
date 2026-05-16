import json
import os
from datetime import date as _date
import prompts


def _path(user_id: str) -> str:
    return f"memory_{user_id}.json"


def load(user_id: str) -> dict:
    try:
        path = _path(user_id)
        if not os.path.exists(path):
            return {"session_count": 0, "facts": []}
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"  [memory] load failed: {e}")
        return {"session_count": 0, "facts": []}


def save(data: dict, user_id: str):
    try:
        with open(_path(user_id), "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  [memory] save failed: {e}")


def _convo_text(messages: list) -> str:
    lines = []
    for m in messages:
        role = m["role"]
        if role in ("system", "tool"):
            continue
        content = m.get("content")
        if not content or not isinstance(content, str):
            continue
        if "<user_context>" in content or "<profile>" in content:
            continue  # skip priming exchange — contains prior session facts, not new conversation
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def extract_and_save(messages: list, client, persisted: dict, new_facts: list, session: int, user_id: str):
    try:
        text = _convo_text(messages)
        if text.strip():
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompts.EXTRACTION_PROMPT},
                    {"role": "user", "content": f"Conversation:\n{text}"},
                ],
            )
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].removeprefix("json").strip()

            try:
                today = _date.today().isoformat()
                for content in json.loads(raw):
                    new_facts.append({
                        "content": content,
                        "source": "conversation",
                        "session": session,
                        "date": today,
                    })
            except (json.JSONDecodeError, TypeError) as e:
                print(f"  [memory] fact parse failed: {e}")

    except Exception as e:
        print(f"  [memory] extract failed: {e}")
    finally:
        persisted["facts"] = persisted["facts"] + new_facts
        persisted["session_count"] = session
        save(persisted, user_id)
