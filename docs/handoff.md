# Team Handoff

## Tanya's

- `src/research_agent/state.py`
- `src/research_agent/graph.py`
- `src/research_agent/nodes.py`
- `src/research_agent/routing.py`
- `src/research_agent/budgets.py`
- `docs/agent_spec.md`
- `docs/graph_design.md`

## Yuliia's/Iryna's Needs to Provide

Implement a custom MCP server in a separate process with tools compatible with
`src/research_agent/tool_contracts.py`.

Required behavior:

- Cache external API responses by request URL/parameters, not by eval task id.
- Distinguish retriable errors from non-retriable errors.
- Return stable paper ids and source metadata.
- Avoid silently dropping missing DOI/arXiv/S2/OpenAlex identifiers.

## Yuliia's/Iryna's Needs to Provide

Replace `eval/tasks.example.json` with at least 30 tasks.

Each task should include:

- task id;
- task text;
- task type;
- expected tool classes;
- forbidden behavior;
- 3-point or 4-point answer rubric;
- notes for manual or LLM-as-judge scoring.

## Shared Contract

No final answer may cite a paper unless that paper is present in `AgentState.papers`
and its supporting claim is present in `AgentState.evidence`.

