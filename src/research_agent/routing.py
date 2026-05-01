"""Conditional routing decisions for the LangGraph agent."""

from __future__ import annotations

from typing import Literal

from research_agent.budgets import budget_stop_reason
from research_agent.state import AgentState, ValidationReport


Route = Literal["search_more", "human_review", "write_answer", "stop_with_budget"]


def route_after_validation(state: AgentState) -> Route:
    """Route based on validation results and runtime budgets."""

    budgets = state.get("budgets")
    if budgets is not None:
        stop_reason = budget_stop_reason(budgets)
        if stop_reason is not None:
            budgets.stop_reason = stop_reason
            return "stop_with_budget"

    validation = state.get("validation", ValidationReport())
    if validation.needs_human_review:
        return "human_review"
    if validation.enough_evidence:
        return "write_answer"
    return "search_more"

