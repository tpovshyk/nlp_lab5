# Lab 5 - Track A Research Agent

Scientific literature research agent.

- Tanya: LangGraph agent architecture, state, routing, interrupts, budgets.
- Yuliia/Iryna: MCP servers and literature data tools.
- Yuliia/Iryna 3: evaluation set, trajectory analysis, ablations, report.

## Scope

It defines the agent design, state schema, graph shape, and integration contracts without hardcoding evaluation
answers or implementing the full assignment end to end.

## Repository Layout

```text
src/research_agent/
  state.py              # Structured LangGraph state schema
  graph.py              # Graph assembly skeleton
  nodes.py              # Node contracts and placeholder logic
  routing.py            # Conditional routing decisions
  budgets.py            # Tool-call / iteration / time budget helpers

docs/
  agent_spec.md         # Agent specification required by the assignment
  graph_design.md       # LangGraph control-flow diagram and explanation
  handoff.md            # What Participants 2 and 3 need from Participant 1

eval/
  tasks.example.json    # Example format only, not the final 30-task set

mcp_literature_server/
  cache.py              # SQLite request-based cache
  literature_tools.py   # arXiv / Semantic Scholar / dedup
  research_server.py    # Tool-exposing server class
  README.md             # Tool contracts and usage
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

