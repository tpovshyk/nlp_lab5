"""Compute aggregate metrics over collected trajectories.

Usage:
    python -m eval.analysis \
        --tasks eval/tasks.json \
        --trajectories eval/trajectories.json \
        --out eval/metrics.json

Optional LLM-as-judge rubric scoring (1-3) via:
    python -m eval.analysis ... --judge

The script writes a JSON with two top-level keys:
  - "summary": aggregate metrics (overall and broken down by task category).
  - "per_task": one row per task with structural metrics and (if --judge) a score.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

# Make sibling packages importable when invoked as a script.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


_ARXIV_RE = re.compile(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b")
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;)\"]+", re.IGNORECASE)


def _final_state(traj: dict) -> dict:
    return traj.get("final_state") or {}


def _tool_calls(traj: dict) -> list[dict]:
    return _final_state(traj).get("tool_calls") or []


def _papers(traj: dict) -> list[dict]:
    return _final_state(traj).get("papers") or []


def _final_answer(traj: dict) -> str:
    return _final_state(traj).get("final_answer") or ""


def _called_tool_classes(traj: dict) -> set[str]:
    classes: set[str] = set()
    for tc in _tool_calls(traj):
        name = tc.get("tool", "")
        if "arxiv" in name:
            classes.add("arxiv_search")
        if "semantic_scholar" in name:
            classes.add("citation_lookup")
        if "deduplicate" in name:
            classes.add("deduplicate")
    return classes


def expected_tool_match(traj: dict, task_def: dict) -> bool:
    """At least one expected tool class was actually called."""
    expected = set(task_def.get("expected_tool_classes") or [])
    if not expected:
        # Tasks that legitimately expect no tool call (e.g., ambiguous tasks
        # the agent should refuse) score True only if the agent also abstained.
        return not _tool_calls(traj)
    return bool(expected & _called_tool_classes(traj))


def hallucinated_citations(traj: dict) -> list[str]:
    """Identifiers cited in the final answer that are not in retrieved papers."""
    answer = _final_answer(traj)
    if not answer:
        return []

    retrieved: set[str] = set()
    for p in _papers(traj):
        for k in ("arxiv_id", "doi", "paper_id", "semantic_scholar_id", "openalex_id"):
            v = p.get(k) if isinstance(p, dict) else None
            if v:
                retrieved.add(str(v).strip().lower())

    cited: set[str] = set()
    for m in _ARXIV_RE.findall(answer):
        cited.add(m.lower())
    for m in _DOI_RE.findall(answer):
        cited.add(m.rstrip(".,);").lower())

    return sorted(cited - retrieved)


def repeated_tool_calls(traj: dict) -> int:
    """Number of redundant duplicates (same tool + args called more than once)."""
    seen: Counter = Counter()
    for tc in _tool_calls(traj):
        key = (
            tc.get("tool", ""),
            json.dumps(tc.get("args", {}), sort_keys=True, default=str),
        )
        seen[key] += 1
    return sum(c - 1 for c in seen.values() if c > 1)


def ungrounded_claim_count(traj: dict, task_def: dict) -> int:
    """Heuristic count of forbidden behaviors triggered.

    For adversarial / ambiguous tasks the rubric says the agent should refuse or
    escalate. We approximate that signal with: did the agent return a confident
    answer (final_answer present, papers list non-empty) for a task whose
    forbidden_behaviors list says it shouldn't?
    """
    if not task_def.get("forbidden_behaviors"):
        return 0
    category = task_def.get("category")
    if category in ("adversarial", "ambiguous") and _papers(traj) and _final_answer(traj):
        return 1
    # For happy-path tasks we already track hallucinated citations separately,
    # so don't double-count here.
    return 0


def per_task_row(traj: dict, task_def: dict) -> dict:
    halluc = hallucinated_citations(traj)
    return {
        "task_id": traj["task_id"],
        "task_type": traj["task_type"],
        "category": traj.get("category") or task_def.get("category"),
        "latency_s": traj.get("latency_s"),
        "tokens": traj.get("tokens"),
        "n_tool_calls": len(_tool_calls(traj)),
        "n_papers": len(_papers(traj)),
        "expected_tool_match": expected_tool_match(traj, task_def),
        "hallucinated_citations": halluc,
        "n_hallucinated": len(halluc),
        "repeated_tool_calls": repeated_tool_calls(traj),
        "ungrounded_signal": ungrounded_claim_count(traj, task_def),
        "has_final_answer": bool(_final_answer(traj)),
        "error": traj.get("error"),
    }


def _avg(xs: Iterable[float]) -> float:
    xs = list(xs)
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}

    summary: dict[str, Any] = {
        "n_tasks": n,
        "n_errors": sum(1 for r in rows if r["error"]),
        "tool_selection_accuracy": round(sum(r["expected_tool_match"] for r in rows) / n, 3),
        "avg_steps": _avg(r["n_tool_calls"] for r in rows),
        "avg_papers": _avg(r["n_papers"] for r in rows),
        "avg_latency_s": _avg(r["latency_s"] or 0 for r in rows),
        "avg_tokens_in": _avg((r.get("tokens") or {}).get("input", 0) for r in rows),
        "avg_tokens_out": _avg((r.get("tokens") or {}).get("output", 0) for r in rows),
        "hallucination_rate": round(sum(1 for r in rows if r["n_hallucinated"]) / n, 3),
        "repeat_call_rate": round(sum(1 for r in rows if r["repeated_tool_calls"]) / n, 3),
        "ungrounded_rate": round(sum(1 for r in rows if r["ungrounded_signal"]) / n, 3),
        "by_category": {},
        "by_task_type": {},
    }

    if any("rubric_score" in r for r in rows):
        scored = [r["rubric_score"] for r in rows if r.get("rubric_score") is not None]
        summary["avg_rubric_score"] = _avg(scored)

    for key in ("category", "task_type"):
        groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            groups[str(r.get(key))].append(r)
        bucket: dict[str, dict] = {}
        for label, items in groups.items():
            m = len(items)
            bucket[label] = {
                "n": m,
                "tool_selection_accuracy": round(
                    sum(r["expected_tool_match"] for r in items) / m, 3
                ),
                "avg_steps": _avg(r["n_tool_calls"] for r in items),
                "hallucination_rate": round(
                    sum(1 for r in items if r["n_hallucinated"]) / m, 3
                ),
                "ungrounded_rate": round(
                    sum(1 for r in items if r["ungrounded_signal"]) / m, 3
                ),
            }
            scored = [r["rubric_score"] for r in items if r.get("rubric_score") is not None]
            if scored:
                bucket[label]["avg_rubric_score"] = _avg(scored)
        summary[f"by_{key}"] = bucket

    return summary


def llm_judge(rows: list[dict], trajectories: list[dict], tasks: dict) -> None:
    """Score each row with an LLM-as-judge against the task rubric (1-3)."""
    from pydantic import BaseModel, Field
    from research_agent.nodes import _build_classifier_llm  # type: ignore

    class RubricScore(BaseModel):
        score: int = Field(description="Integer 1-3 per the rubric.")
        reasoning: str = Field(description="One- or two-sentence justification.")
        violations: list[str] = Field(
            default_factory=list,
            description="Forbidden behaviors observed in the answer.",
        )

    llm = _build_classifier_llm()
    judge = llm.with_structured_output(RubricScore)

    for row, traj in zip(rows, trajectories):
        task_def = tasks.get(row["task_id"], {})
        if not task_def.get("rubric"):
            continue
        prompt = (
            "You are a strict rubric grader for a research agent. Score the agent's "
            "final answer against the rubric. Score 1 (worst) to 3 (best).\n\n"
            f"Task prompt: {task_def['prompt']}\n\n"
            f"Rubric:\n{json.dumps(task_def['rubric'], indent=2, ensure_ascii=False)}\n\n"
            f"Forbidden behaviors:\n"
            f"{json.dumps(task_def.get('forbidden_behaviors', []), indent=2, ensure_ascii=False)}\n\n"
            f"Agent answer:\n{(_final_answer(traj) or '(empty)')[:3500]}\n\n"
            f"Tool calls made: {len(_tool_calls(traj))}\n"
            f"Papers retrieved: {len(_papers(traj))}\n"
            f"Hallucinated identifiers (already detected structurally): "
            f"{row['hallucinated_citations']}\n"
        )
        try:
            res = judge.invoke(prompt)
            row["rubric_score"] = int(res.score)
            row["rubric_reasoning"] = res.reasoning
            row["rubric_violations"] = list(res.violations)
        except Exception as exc:  # noqa: BLE001
            row["rubric_score"] = None
            row["rubric_reasoning"] = f"judge_error: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="eval/tasks.json")
    parser.add_argument("--trajectories", default="eval/trajectories.json")
    parser.add_argument("--out", default="eval/metrics.json")
    parser.add_argument(
        "--judge", action="store_true",
        help="Use the configured LLM to score each answer against its rubric.",
    )
    args = parser.parse_args()

    tasks = {t["id"]: t for t in json.loads(Path(args.tasks).read_text(encoding="utf-8"))}
    trajectories = json.loads(Path(args.trajectories).read_text(encoding="utf-8"))

    rows = [per_task_row(t, tasks.get(t["task_id"], {})) for t in trajectories]

    if args.judge:
        llm_judge(rows, trajectories, tasks)

    out = {"summary": summarize(rows), "per_task": rows}
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
