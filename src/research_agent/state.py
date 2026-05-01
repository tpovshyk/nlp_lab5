"""Structured state for the Track A LangGraph agent.

The assignment explicitly asks us not to dump everything into one messages list.
This module separates durable research artifacts from transient scratchpad data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, TypedDict


class ResearchTaskType(StrEnum):
    """Supported task families for Track A."""

    MOST_CITED = "most_cited"
    CLAIM_EVIDENCE = "claim_evidence"
    PAPER_COMPARISON = "paper_comparison"
    LITERATURE_REVIEW = "literature_review"
    UNKNOWN = "unknown"

@dataclass
class PaperRecord:
    """A paper retrieved through MCP tools."""

    paper_id: str
    title: str
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    citation_count: int | None = None
    source_tool: str = ""


@dataclass
class EvidenceItem:
    """Grounding evidence used by the final answer."""

    claim: str
    paper_id: str
    support_type: Literal["supports", "contradicts", "qualifies", "background"]
    quote_or_summary: str
    source_tool_call_id: str


@dataclass
class ToolCallRecord:
    """Machine-readable trajectory event for a tool call."""

    call_id: str
    tool_name: str
    arguments: dict
    status: Literal["ok", "retriable_error", "non_retriable_error"]
    latency_ms: int | None = None
    error_message: str | None = None


@dataclass
class BudgetState:
    """Runtime limits used to keep cycles safe."""

    max_iterations: int = 8
    max_tool_calls: int = 20
    max_wall_clock_seconds: int = 180
    iteration_count: int = 0
    tool_call_count: int = 0
    started_at_epoch_seconds: float | None = None
    stop_reason: str | None = None


@dataclass
class ValidationReport:
    """Grounding and quality checks before final output."""

    enough_evidence: bool = False
    ungrounded_claims: list[str] = field(default_factory=list)
    missing_identifiers: list[str] = field(default_factory=list)
    needs_human_review: bool = False
    notes: list[str] = field(default_factory=list)


class AgentState(TypedDict, total=False):
    """LangGraph state channels.

    Reducers can be added in graph.py once concrete LangGraph versions are chosen.
    """

    user_question: str
    task_type: ResearchTaskType
    plan: list[str]
    papers: list[PaperRecord]
    evidence: list[EvidenceItem]
    tool_calls: list[ToolCallRecord]
    transient_notes: list[str]
    budgets: BudgetState
    validation: ValidationReport
    final_answer: str
