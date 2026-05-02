# Evaluation Pipeline

End-to-end harness for grading the Track A research agent against a fixed set
of tasks, computing structural metrics, and running ablation studies.

## Files

| File | Purpose |
| --- | --- |
| `tasks.json` | 30 evaluation tasks across happy / ambiguous / adversarial categories. Each task carries a 3-point rubric and a list of forbidden behaviors. |
| `tasks.example.json` | Original 1-task example kept for reference. |
| `collect_trajectories.py` | Runs the agent on every task, captures inputs / outputs / tool calls / latency / token usage. Writes trajectories incrementally. |
| `analysis.py` | Aggregates structural metrics and (optionally) runs LLM-as-judge rubric scoring (1-3) per task. |
| `ablations.py` | Driver that runs collection + analysis under different env configurations (model, prompt, graph). |

## Task design

30 tasks, three categories (the `category` field on each task):

* **happy** (15) — straightforward queries with clear answer paths. The agent
  should call the expected tool classes, ground all citations in tool output,
  and return a structured answer.
* **ambiguous** (10) — underspecified queries (no year, no IDs, subjective
  superlatives, missing referent). The agent should ask for clarification or
  return transparently broad results, not fabricate constraints.
* **adversarial** (5) — impossible or fictional asks (future dates, fake IDs,
  unestablished hybrid fields, "prove P=NP"). The agent should refuse or
  escalate, not fabricate.

Every task specifies `expected_tool_classes`, `forbidden_behaviors`, and a
3-point rubric. Note the contract from `docs/handoff.md`: no hardcoded answers,
no task-ID-keyed cache, no special-casing IDs that appear in the eval set.

## Running

Install the agent + MCP deps once:

```bash
pip install -e ".[agent,mcp]"
```

Set the API keys you need in `.env` (see `.env.example`).

### Collect trajectories

```bash
python -m eval.collect_trajectories \
    --tasks eval/tasks.json \
    --out eval/trajectories.json \
    --run-label baseline
```

A small smoke test (first 3 tasks):

```bash
python -m eval.collect_trajectories --limit 3
```

### Compute metrics

```bash
python -m eval.analysis \
    --tasks eval/tasks.json \
    --trajectories eval/trajectories.json \
    --out eval/metrics.json
```

To also run an LLM rubric grader (uses the same provider/model env as the agent):

```bash
python -m eval.analysis --judge
```

### Ablations

```bash
python -m eval.ablations --out-dir eval/ablations
```

Or pick a subset:

```bash
python -m eval.ablations --variants baseline graph_no_validator prompt_minimal
```

Variants currently defined (`eval/ablations.py`):

* `baseline` — current configuration.
* `model_haiku`, `model_sonnet` — model ablation across two Anthropic tiers.
* `model_gpt4o`, `model_gemini` — cross-provider model ablation. Requires
  `pip install -e ".[ablation]"` plus the relevant API keys.
* `prompt_minimal`, `prompt_verbose` — `classify_task` prompt rewrites.
* `graph_no_validator` — graph ablation that skips `validate_evidence`.

Each variant writes its own `trajectories_<variant>.json` and
`metrics_<variant>.json`; the driver also writes `summary.json` with a
side-by-side comparison.

Cross-variant env wiring lives in three places:

* `MODEL_PROVIDER` / `MODEL_NAME` — read by `_build_classifier_llm` in
  `src/research_agent/nodes.py`.
* `CLASSIFY_PROMPT_VARIANT` — picks a template from `_CLASSIFY_PROMPTS` in the
  same file (`default` / `minimal` / `verbose`).
* `GRAPH_VARIANT` — read by `build_graph` in `src/research_agent/graph.py`.

## Metrics

Structural metrics are computed deterministically from the trajectory:

| Metric | Definition |
| --- | --- |
| `tool_selection_accuracy` | Fraction of tasks where at least one of the task's `expected_tool_classes` was actually invoked (or where the task expected no tool call and the agent called none). |
| `avg_steps` | Mean number of tool calls per task. |
| `avg_papers` | Mean papers retained in final state. |
| `avg_latency_s` | Mean wall-clock seconds per task (driver-side, not model-side). |
| `avg_tokens_in/out` | Mean token usage from LangChain `usage_metadata`, when the provider exposes it. |
| `hallucination_rate` | Fraction of tasks where the final answer contained an arXiv ID or DOI not present in retrieved papers. |
| `repeat_call_rate` | Fraction of tasks with at least one duplicate (same tool + same args) call. |
| `ungrounded_rate` | Fraction of ambiguous / adversarial tasks where the agent returned a confident answer instead of escalating / refusing. |

LLM-as-judge (`--judge`) adds `rubric_score` (1-3) and `rubric_reasoning` per
task, plus `avg_rubric_score` aggregates.

## Caching note

`mcp_literature_server` keys its cache by request parameters, not by task ID
(see `mcp_literature_server/README.md`). After the first full run, repeat runs
should be much faster because arXiv / Semantic Scholar responses are reused.
This is required by the assignment contract: the eval set must work with a
cold cache, but a warm cache is allowed.
