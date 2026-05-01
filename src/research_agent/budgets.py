"""Budget helpers for safe graph cycles."""

from __future__ import annotations

import time

from research_agent.state import BudgetState


def start_budget_clock(budgets: BudgetState | None) -> BudgetState:
    """Return a budget object with a start time."""

    budget_state = budgets or BudgetState()
    if budget_state.started_at_epoch_seconds is None:
        budget_state.started_at_epoch_seconds = time.time()
    return budget_state


def budget_stop_reason(budgets: BudgetState) -> str | None:
    """Return a stop reason if a budget has been exceeded."""

    if budgets.iteration_count >= budgets.max_iterations:
        return "max_iterations"
    if budgets.tool_call_count >= budgets.max_tool_calls:
        return "max_tool_calls"
    if budgets.started_at_epoch_seconds is not None:
        elapsed = time.time() - budgets.started_at_epoch_seconds
        if elapsed >= budgets.max_wall_clock_seconds:
            return "max_wall_clock_seconds"
    return None

