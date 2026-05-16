# Setup & Running

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- OpenAI API key

## Install

```bash
uv sync
```

## Configure

```bash
export OPENAI_API_KEY=your_key_here
```

## Run Session 1

Ensure `CURRENT_SESSION = 1` in `tools.py` (default).

```bash
uv run python agent.py
```

Type the messages from `sessions.md` in order. Type `exit` when done.  
Memory is written to `memory_priya_sharma.json` automatically on exit.

## Run Session 2

Open `tools.py` and change line 12:

```python
CURRENT_SESSION = 2
```

Then run again:

```bash
uv run python agent.py
```

The agent will load the memory from Session 1 and respond accordingly.

## Files

```
agent.py      — ReAct loop, intent classifier, session management
memory.py     — disk persistence, end-of-session fact extraction
prompts.py    — all prompts: system, classifier, extraction, user context
tools.py      — provided mock tools, do not modify
sessions.md   — provided session scripts, do not modify
```
