"""Run the research agent on every eval task and capture trajectories.

Usage:
    python -m eval.collect_trajectories \
        --tasks eval/tasks.json \
        --out eval/trajectories.json \
        --run-label baseline

The script writes trajectories incrementally so a crash mid-run keeps the
already-completed tasks. Each trajectory captures the prompt, the agent's
final state (papers, tool calls, validation, final answer), per-run latency,
and token usage if the LLM provider exposes it via callbacks.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so `mcp_literature_server` resolves the
# same way it does when running the bot from the project root.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research_agent.graph import build_graph  # noqa: E402

logger = logging.getLogger(__name__)


def _to_jsonable(obj: Any) -> Any:
    """Convert dataclasses / enums / nested structures into JSON-safe values."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Enum):
        return obj.value
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    return str(obj)


class TokenTracker:
    """LangChain callback that accumulates token usage across LLM calls."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def _try_register(self, agent_kwargs: dict) -> None:
        """Wire this tracker into agent.invoke kwargs as a callback."""
        try:
            from langchain_core.callbacks import BaseCallbackHandler
        except ImportError:
            return

        outer = self

        class _Handler(BaseCallbackHandler):
            def on_llm_end(self, response, **_kwargs):  # type: ignore[no-untyped-def]
                outer.calls += 1
                try:
                    for gen_list in response.generations:
                        for gen in gen_list:
                            msg = getattr(gen, "message", None)
                            usage = getattr(msg, "usage_metadata", None) if msg else None
                            if usage:
                                outer.input_tokens += int(usage.get("input_tokens", 0) or 0)
                                outer.output_tokens += int(usage.get("output_tokens", 0) or 0)
                except Exception:
                    pass

        agent_kwargs.setdefault("config", {}).setdefault("callbacks", []).append(_Handler())


def run_task(agent: Any, task: dict, run_label: str) -> dict:
    prompt = task["prompt"]
    tracker = TokenTracker()
    invoke_kwargs: dict[str, Any] = {}
    tracker._try_register(invoke_kwargs)

    start = time.perf_counter()
    error: str | None = None
    final_state: dict[str, Any] = {}
    try:
        final_state = agent.invoke({"user_question": prompt}, **invoke_kwargs)
    except Exception as exc:  # noqa: BLE001 - we capture and continue
        logger.exception("Task %s raised", task["id"])
        error = f"{type(exc).__name__}: {exc}"
    latency = time.perf_counter() - start

    return {
        "task_id": task["id"],
        "task_type": task["task_type"],
        "category": task.get("category"),
        "prompt": prompt,
        "run_label": run_label,
        "model": os.getenv("MODEL_NAME", "claude-haiku-4-5-20251001"),
        "model_provider": os.getenv("MODEL_PROVIDER", "anthropic"),
        "latency_s": round(latency, 3),
        "tokens": {
            "input": tracker.input_tokens,
            "output": tracker.output_tokens,
            "llm_calls": tracker.calls,
        },
        "error": error,
        "final_state": _to_jsonable(final_state),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="eval/tasks.json")
    parser.add_argument("--out", default="eval/trajectories.json")
    parser.add_argument("--run-label", default="baseline")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run only the first N tasks (smoke test).",
    )
    parser.add_argument(
        "--graph-variant", default=None,
        help="Override GRAPH_VARIANT (e.g. 'no_validator').",
    )
    args = parser.parse_args()

    tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    if args.limit:
        tasks = tasks[: args.limit]

    agent = build_graph(variant=args.graph_variant)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trajectories: list[dict] = []
    for i, task in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] {task['id']}: {task['prompt'][:80]}")
        traj = run_task(agent, task, args.run_label)
        trajectories.append(traj)
        out_path.write_text(
            json.dumps(trajectories, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"\nSaved {len(trajectories)} trajectories to {out_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    main()
