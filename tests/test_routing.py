from research_agent.routing import route_after_validation
from research_agent.state import AgentState, BudgetState, ValidationReport


def test_routes_to_write_answer_when_evidence_is_enough() -> None:
    state: AgentState = {"validation": ValidationReport(enough_evidence=True)}

    assert route_after_validation(state) == "write_answer"


def test_routes_to_human_review_when_requested() -> None:
    state: AgentState = {
        "validation": ValidationReport(enough_evidence=False, needs_human_review=True)
    }

    assert route_after_validation(state) == "human_review"


def test_routes_to_budget_stop_when_iteration_cap_hit() -> None:
    state: AgentState = {"budgets": BudgetState(max_iterations=1, iteration_count=1)}

    assert route_after_validation(state) == "stop_with_budget"

