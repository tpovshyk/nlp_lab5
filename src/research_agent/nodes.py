"""LangGraph node contracts for Participant 1.

These functions are intentionally small placeholders. They show the state changes and
handoff boundaries without replacing the student's own implementation work.
"""

from __future__ import annotations

from research_agent.budgets import start_budget_clock
from research_agent.state import AgentState, BudgetState, ResearchTaskType, ValidationReport


def initialize_run(state: AgentState) -> AgentState:
    """Initialize budgets and scratch fields for a run."""

    return {
        **state,
        "budgets": start_budget_clock(state.get("budgets", BudgetState())),
        "plan": state.get("plan", []),
        "papers": state.get("papers", []),
        "evidence": state.get("evidence", []),
        "tool_calls": state.get("tool_calls", []),
        "transient_notes": state.get("transient_notes", []),
    }


def classify_task(state: AgentState) -> AgentState:
    """Classify the research question into a Track A task family.

    Replace this heuristic with an LLM structured-output call in the real graph.
    """

    question = state["user_question"].lower()
    if "most-cited" in question or "most cited" in question:
        task_type = ResearchTaskType.MOST_CITED
    elif "support" in question or "contradict" in question:
        task_type = ResearchTaskType.CLAIM_EVIDENCE
    elif "cites" in question or "share authors" in question:
        task_type = ResearchTaskType.PAPER_COMPARISON
    elif "literature-review" in question or "literature review" in question:
        task_type = ResearchTaskType.LITERATURE_REVIEW
    else:
        task_type = ResearchTaskType.UNKNOWN

    return {**state, "task_type": task_type}


def plan_search(state: AgentState) -> AgentState:
    """Create a short search plan.

    The final implementation should ask the chosen LLM for a structured plan and
    keep it compact enough for trajectory review.
    """

    task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
    plan = [
        f"Identify source papers for task type: {task_type}",
        "Retrieve paper metadata through MCP tools only.",
        "Validate that final citations come from retrieved tool results.",
    ]
    return {**state, "plan": plan}


def search_papers(state: AgentState) -> AgentState:
    """Call literature MCP tools.

    Participant 2 will provide the concrete MCP tools. Participant 1 should wire this
    node to discovered tools, record each call in state.tool_calls, and update papers.
    """

    budgets = state.get("budgets", BudgetState())
    budgets.iteration_count += 1
    return {
        **state,
        "budgets": budgets,
        "transient_notes": [
            *state.get("transient_notes", []),
            "search_papers placeholder: connect to custom MCP tools here.",
        ],
    }


def validate_evidence(state: AgentState) -> AgentState:
    """Check whether the current paper/evidence set is enough."""

    papers = state.get("papers", [])
    evidence = state.get("evidence", [])
    validation = ValidationReport(
        enough_evidence=bool(papers and evidence),
        needs_human_review=state.get("task_type") == ResearchTaskType.UNKNOWN,
        notes=[] if papers else ["No retrieved papers yet."],
    )
    return {**state, "validation": validation}


def write_answer(state: AgentState) -> AgentState:
    """Produce the final answer from validated evidence only."""

    validation = state.get("validation", ValidationReport())
    if validation.ungrounded_claims:
        answer = "I cannot provide a final answer because some claims are ungrounded."
    elif state.get("papers"):
        answer = "Final answer placeholder: summarize only validated retrieved papers."
    else:
        answer = "No grounded answer could be produced from retrieved papers."
    return {**state, "final_answer": answer}


def stop_with_budget_message(state: AgentState) -> AgentState:
    """Exit cleanly when a budget is hit."""

    budgets = state.get("budgets", BudgetState(stop_reason="unknown_budget"))
    return {
        **state,
        "final_answer": f"Stopped because budget was reached: {budgets.stop_reason}.",
    }

