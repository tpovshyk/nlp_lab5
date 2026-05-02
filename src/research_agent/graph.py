"""Graph assembly skeleton.

This file documents the intended LangGraph shape for Participant 1. Keep concrete
provider calls and MCP client setup outside module import time so demo configuration
can be changed easily.
"""

from __future__ import annotations

import os
from typing import Any

from research_agent.nodes import (
    classify_task,
    initialize_run,
    plan_search,
    search_papers,
    stop_with_budget_message,
    validate_evidence,
    write_answer,
)
from research_agent.routing import route_after_validation
from research_agent.state import AgentState


def build_graph(
    checkpointer: Any | None = None,
    variant: str | None = None,
) -> Any:
    """Build and compile the LangGraph StateGraph.

    Variants (also picked up from the GRAPH_VARIANT env var):
      - default / None: full graph with validator and conditional re-search.
      - "no_validator": skip the validator node; search_papers feeds write_answer
        directly. Used for graph ablation studies.
    """

    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "Install the agent dependencies first: pip install -e '.[agent]'"
        ) from exc

    variant = variant or os.environ.get("GRAPH_VARIANT")

    graph = StateGraph(AgentState)
    graph.add_node("initialize_run", initialize_run)
    graph.add_node("classify_task", classify_task)
    graph.add_node("plan_search", plan_search)
    graph.add_node("search_papers", search_papers)
    graph.add_node("write_answer", write_answer)
    graph.add_node("stop_with_budget", stop_with_budget_message)

    graph.set_entry_point("initialize_run")
    graph.add_edge("initialize_run", "classify_task")
    graph.add_edge("classify_task", "plan_search")
    graph.add_edge("plan_search", "search_papers")

    if variant == "no_validator":
        graph.add_edge("search_papers", "write_answer")
    else:
        graph.add_node("validate_evidence", validate_evidence)
        graph.add_edge("search_papers", "validate_evidence")
        graph.add_conditional_edges(
            "validate_evidence",
            route_after_validation,
            {
                "search_more": "search_papers",
                "human_review": "write_answer",
                "write_answer": "write_answer",
                "stop_with_budget": "stop_with_budget",
            },
        )

    graph.add_edge("write_answer", END)
    graph.add_edge("stop_with_budget", END)

    return graph.compile(checkpointer=checkpointer)
