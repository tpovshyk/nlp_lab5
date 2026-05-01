"""Expected MCP tool contracts for Participant 2.

These models document the arguments and return shapes that Participant 1's graph
expects from the custom literature MCP server. The server itself should run in a
separate process during the demo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from research_agent.state import PaperRecord


@dataclass
class SearchArxivArgs:
    query: str
    year_from: int | None = None
    max_results: int = 10


@dataclass
class SearchArxivResult:
    papers: list[PaperRecord]
    cached: bool


@dataclass
class GetSemanticScholarPaperArgs:
    paper_id_or_title: str
    include_references: bool = True
    include_citations: bool = True


@dataclass
class PaperRelationshipResult:
    paper: PaperRecord
    references: list[PaperRecord] = field(default_factory=list)
    citations: list[PaperRecord] = field(default_factory=list)
    cached: bool


@dataclass
class DeduplicatePapersArgs:
    papers: list[PaperRecord]


@dataclass
class DeduplicatePapersResult:
    papers: list[PaperRecord]
    duplicate_groups: list[list[str]] = field(default_factory=list)


EXPECTED_CUSTOM_MCP_TOOLS = {
    "search_arxiv": {
        "args": SearchArxivArgs,
        "result": SearchArxivResult,
        "side_effects": "Reads/writes HTTP response cache keyed by API request.",
    },
    "get_semantic_scholar_paper": {
        "args": GetSemanticScholarPaperArgs,
        "result": PaperRelationshipResult,
        "side_effects": "Reads/writes HTTP response cache keyed by API request.",
    },
    "deduplicate_papers": {
        "args": DeduplicatePapersArgs,
        "result": DeduplicatePapersResult,
        "side_effects": "May write local deduplication notes/cache.",
    },
}
