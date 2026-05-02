"""Run all three ablation studies: model, prompt, graph.

Usage:
    python -m eval.ablations \
        --tasks eval/tasks.json \
        --out-dir eval/ablations \
        --variants baseline model_haiku model_sonnet \
                   prompt_minimal prompt_verbose graph_no_validator

Each variant is run as a subprocess so its env (MODEL_NAME / MODEL_PROVIDER /
CLASSIFY_PROMPT_VARIANT / GRAPH_VARIANT) is fully isolated. After every run the
analysis script computes structural metrics; pass --judge to also run rubric
scoring per variant.

Cross-provider variants (model_gpt4o, model_gemini) require:
    pip install -e ".[ablation]"
and the corresponding API keys (OPENAI_API_KEY, GOOGLE_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


VARIANTS: dict[str, dict[str, str]] = {
    "baseline": {},
    # Model ablation: same graph, different LLMs.
    "model_haiku": {"MODEL_PROVIDER": "anthropic", "MODEL_NAME": "claude-haiku-4-5-20251001"},
    "model_sonnet": {"MODEL_PROVIDER": "anthropic", "MODEL_NAME": "claude-sonnet-4-6"},
    "model_gpt4o": {"MODEL_PROVIDER": "openai", "MODEL_NAME": "gpt-4o-mini"},
    "model_gemini": {"MODEL_PROVIDER": "google", "MODEL_NAME": "gemini-1.5-flash"},
    # Prompt / tool-description ablation: same model and graph, different prompt.
    "prompt_minimal": {"CLASSIFY_PROMPT_VARIANT": "minimal"},
    "prompt_verbose": {"CLASSIFY_PROMPT_VARIANT": "verbose"},
    # Graph ablation: skip the validator node entirely.
    "graph_no_validator": {"GRAPH_VARIANT": "no_validator"},
}


def _run(cmd: list[str], env: dict[str, str]) -> int:
    print(f"[run] {' '.join(cmd)}")
    proc = subprocess.run(cmd, env=env, check=False)
    return proc.returncode


def run_variant(
    name: str,
    overrides: dict[str, str],
    tasks_path: str,
    out_dir: Path,
    judge: bool,
    limit: int | None,
) -> dict:
    env = {**os.environ, **overrides}

    traj_path = out_dir / f"trajectories_{name}.json"
    metrics_path = out_dir / f"metrics_{name}.json"

    collect_cmd = [
        sys.executable, "-m", "eval.collect_trajectories",
        "--tasks", tasks_path,
        "--out", str(traj_path),
        "--run-label", name,
    ]
    if limit is not None:
        collect_cmd += ["--limit", str(limit)]
    rc = _run(collect_cmd, env)
    if rc != 0:
        return {"variant": name, "error": f"collect exited {rc}", "config": overrides}

    analysis_cmd = [
        sys.executable, "-m", "eval.analysis",
        "--tasks", tasks_path,
        "--trajectories", str(traj_path),
        "--out", str(metrics_path),
    ]
    if judge:
        analysis_cmd.append("--judge")
    _run(analysis_cmd, env)

    summary: dict = {}
    if metrics_path.exists():
        summary = json.loads(metrics_path.read_text(encoding="utf-8")).get("summary", {})

    return {"variant": name, "config": overrides, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="eval/tasks.json")
    parser.add_argument("--out-dir", default="eval/ablations")
    parser.add_argument(
        "--variants", nargs="+", default=[
            "baseline",
            "model_haiku", "model_sonnet",
            "prompt_minimal", "prompt_verbose",
            "graph_no_validator",
        ],
        help="Subset of variants to run. See VARIANTS in this file.",
    )
    parser.add_argument(
        "--judge", action="store_true",
        help="Also run LLM-as-judge rubric scoring for each variant.",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run only the first N tasks per variant (smoke test).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for name in args.variants:
        if name not in VARIANTS:
            print(f"Unknown variant: {name}; known: {list(VARIANTS)}")
            continue
        results.append(run_variant(
            name, VARIANTS[name], args.tasks, out_dir, args.judge, args.limit,
        ))

    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote ablation summary to {summary_path}")
    print(json.dumps(
        [{"variant": r["variant"], "summary": r.get("summary", {})} for r in results],
        indent=2, ensure_ascii=False,
    ))


if __name__ == "__main__":
    main()
