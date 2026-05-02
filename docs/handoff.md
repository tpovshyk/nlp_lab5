# Team Handoff

## Participant 1 (Tanya) — Graph & State Design ✅

**Status: COMPLETE**

Provided files in `src/research_agent/`:
- `state.py` — Structured LangGraph state schema with durable artifacts + transient scratchpad
- `graph.py` — Graph assembly with nodes and conditional routing
- `nodes.py` — Node contracts and placeholder logic
- `routing.py` — Conditional routing decisions (validate → search_more | write_answer | human_review | stop)
- `budgets.py` — Runtime budget helpers (iteration, tool call, wall-clock limits)
- `tool_contracts.py` — Expected MCP tool contracts (SearchArxivArgs, GetSemanticScholarPaperArgs, etc.)

Documentation:
- `docs/agent_spec.md` — Agent specification (inputs, outputs, tools, stopping criteria, failure modes)
- `docs/graph_design.md` — Control-flow diagram and architecture justification

## Participant 2 (Yuliia/Iryna) — MCP Server & Literature Tools ✅

**Status: COMPLETE**

Custom MCP server in `mcp/`:
- `server.py` — Main MCP server entry point (exposes 3 tools via stdio)
- `literature_tools.py` — Tool implementations:
  - `ArxivSearcher` — Search arXiv API with caching and rate limiting (0.5s between requests)
  - `SemanticScholarClient` — Fetch paper metadata + citations/references with caching (1s between requests)
  - `PaperDeduplicator` — Deduplicate by DOI, arXiv ID, or normalized title
- `cache.py` — Request-based SQLite caching (keyed by request params, not task ID)
- `__init__.py` — Package init
- `__main__.py` — Entry point for `python -m mcp`

Tests:
- `tests/test_literature_tools.py` — 12 passing tests for cache, deduplication, error handling

Documentation:
- `mcp/README.md` — Full tool contract, caching strategy, rate limits, error handling
- `mcp/INTEGRATION.md` — Step-by-step guide to connect server to agent

**Tool Contracts Implemented:**
- ✅ `search_arxiv(query, year_from, max_results)` → `{papers, cached}`
- ✅ `get_semantic_scholar_paper(paper_id_or_title, include_references, include_citations)` → `{paper, references, citations, cached}`
- ✅ `deduplicate_papers(papers)` → `{papers, duplicate_groups}`

**Error Handling:**
- ✅ Distinguishes retriable (network, rate limit) from non-retriable (invalid query, 404, parsing)
- ✅ Returns error with `is_retriable` flag for agent-level retry logic

**Caching:**
- ✅ Request-based (not task-based) — identical requests from different tasks reuse cache
- ✅ SQLite backend at `.cache/api_cache.db`
- ✅ Survives process restart

### Next Steps for Participant 2
1. Test MCP server against live arXiv and Semantic Scholar APIs
2. Pre-populate cache with common queries for evaluation
3. Verify rate limit behavior (add sleeps if API responses are slow)
4. Document any additional tools needed for evaluation set

### How to Start the Server
```bash
cd /Users/mac/nlp_lab5
python -m mcp --cache-dir /tmp/cache
```

See `INTEGRATION.md` for full agent-to-server connection patterns.

## Participant 3 (Yuliia/Iryna) — Evaluation & Report ⏳

**Status: NOT STARTED**

### To Provide

1. **Evaluation Set** (`eval/tasks.json`): At least 30 tasks covering:
   - Happy paths: straightforward queries with clear answers
   - Ambiguous queries: underspecified tasks requiring clarification
   - Adversarial tasks: 3+ cases where agent should refuse or escalate
     - (e.g., "Find most-cited papers on nonexistent topic X after 2100")
   - Each task needs:
     - `id`, `prompt`, `task_type`, `expected_tool_classes`, `forbidden_behaviors`
     - Rubric: 3-point or 4-point scale with clear criteria
     - Notes for manual/LLM-as-judge scoring

2. **Trajectory Logging** (`eval/collect_trajectories.py`):
   - Run agent on all 30 tasks
   - Capture per-step: inputs, outputs, tool calls, results, token counts, latency
   - Store as machine-readable JSON or CSV
   - Format: one trajectory file per task or one mega-file with indexing

3. **Metrics & Analysis** (`eval/analysis.py`):
   - Aggregate metrics: final-answer quality, tool-selection accuracy, steps per task, tokens/cost/latency
   - Trajectory-level metrics: rate of hallucinated citations, ungrounded claims, repeated tool calls
   - 3+ concrete failure modes with annotated traces
   - Comparison table: how agent performs on each task type

4. **Ablation Studies** (`eval/ablations.py`):
   - **Model ablation**: Same graph with 2+ different LLMs (e.g., Claude 3.5 Sonnet vs. GPT-4.1)
     - Report: final-answer quality, cost (USD), latency per task
   - **Prompt/tool-description ablation**: Rewrite system prompt or tool descriptions materially differently
     - Measure tool-selection accuracy impact
   - **Graph ablation**: Remove or modify one structural element (e.g., skip validator, combine search + validate)
     - Compare aggregate quality
   - Keep evaluation set and random seeds fixed across all ablations

5. **Final Report** (`README.md` or `REPORT.md`):
   - Agent specification + control-flow diagram
   - Tool contracts (including MCP server)
   - Evaluation set design and rubric
   - Aggregate metrics for every experiment
   - 3+ annotated failure traces
   - Ablation results and insights
   - Conclusions and what you'd change given more time

### Shared Contract (Enforced in Demo)

**No hardcoding.** Strictly forbidden:
- ❌ Hardcoding eval task answers into prompts or post-processing
- ❌ Cache keys that are task-ID specific
- ❌ Special-casing arXiv IDs, paper titles, or queries that appear in eval set
- ❌ Over-fitting to your own eval set design

The Lecturer will run tasks from your eval set **and** propose new unseen tasks on the spot during defense. A narrow eval set designed to inflate metrics will not protect you.

**Cache compliance:**
- Cache key = request parameters (query, year_from, max_results), NOT task ID
- The agent must work with a cold cache (or at least not assume cache is always warm)

### Example Eval Task

```json
{
  "id": "most_cited_001",
  "task_type": "most_cited",
  "prompt": "Find the 3 most-cited papers on retrieval-augmented generation published after 2020. For each, provide a one-sentence summary and DOI or arXiv ID.",
  "expected_tool_classes": ["arxiv_search", "citation_lookup"],
  "forbidden_behaviors": [
    "Citing papers not retrieved by tools",
    "Reporting citation counts without a source",
    "Ignoring the year constraint"
  ],
  "rubric": {
    "1": "Mostly incorrect or ungrounded citations.",
    "2": "Relevant papers but missing identifiers or weak grounding.",
    "3": "3 relevant grounded papers with correct identifiers and summaries."
  },
  "notes": "Check that all reported arXiv IDs or DOIs can be verified against tool results."
}
```

### Recommended LLM for Primary Evaluation

- Claude 3.5 Sonnet (recommended for Track A — strong reasoning + citations)
- GPT-4.1 or GPT-5
- Gemini 2.5 Flash

Must disclose model and version in report. Re-run evaluation during defense (bring cached trajectories as fallback).

### Connecting to Agent

Participant 1's graph is a scaffold. Participant 3 should:
1. Wire LLM into nodes that currently have placeholders (e.g., `classify_task`, `plan_search`)
2. Connect MCP server (from Participant 2) to `search_papers` node
3. Implement `validate_evidence` node with citation grounding checks
4. Implement `write_answer` node that synthesizes final output with inline citations

See `mcp/INTEGRATION.md` for connection patterns.

## Shared Responsibilities

### Code Quality
- Logging from day one (LangSmith, OpenTelemetry, or structured JSON)
- Type hints + mypy strict mode
- Docstrings for all public functions

### Testing
- Unit tests for each component (graph nodes, tools, validators)
- Integration tests for agent + MCP server
- No hardcoded eval-set answers

### Defense Preparation
- Rehearse failure paths (not just happy path)
- Have cached trajectories ready in case API fails during demo
- Be ready to explain:
  - Why this architecture over alternatives
  - What failure modes you expect and how you handle them
  - How metrics were computed and what they mean
  - What ablations revealed and why

## Timeline

- **Code deadline**: 29 Apr (today or tomorrow)
- **Demo/Defense deadline**: 29 Apr
- **Lecture rubric**:
  - 7 pts: Overall correctness (code quality, metrics, eval set design)
  - 5 pts: Live demo (running agent on Lecturer's tasks + human-in-the-loop)
  - 3 pts: Theory + practical exercise questions

## Contact & Questions

- Participant 1 (Tanya) → State, graph, routing, budgets
- Participant 2 (Yuliia/Iryna) → MCP server, literature tools, caching
- Participant 3 (Yuliia/Iryna) → Evaluation, metrics, ablations, report


