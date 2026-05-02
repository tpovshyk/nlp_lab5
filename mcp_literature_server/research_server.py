"""Literature data tools server for Track A research agent.

This server exposes three tools for literature research:
  1. search_arxiv - Search arXiv API for papers
  2. get_semantic_scholar_paper - Fetch paper metadata and relationships
  3. deduplicate_papers - Merge duplicate paper records

This is a simple server that can be called directly from the agent.
For MCP integration, wrap these as MCP tools using the mcp SDK.
"""

import json
import logging
from typing import Any, Dict, Optional, Callable

from .cache import RequestCache
from .literature_tools import (
    ArxivSearcher,
    SemanticScholarClient,
    PaperDeduplicator,
    LiteratureToolsError,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ResearchAgentServer:
    """Server for literature research tools."""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache = RequestCache(cache_dir)
        self.arxiv = ArxivSearcher(self.cache)
        self.semantic_scholar = SemanticScholarClient(self.cache)
        self.deduplicator = PaperDeduplicator(self.cache)
        
        logger.info(f"Initialized ResearchAgentServer with cache at {cache_dir}")

    def search_arxiv(
        self,
        query: str,
        year_from: Optional[int] = None,
        max_results: int = 10,
    ) -> Dict[str, Any]:
        """
        Search arXiv for papers.
        
        Args:
            query: Search query string
            year_from: Optional minimum year filter
            max_results: Max number of results (default 10, max 100)
        
        Returns:
            dict with papers list and cached flag
        """
        try:
            logger.info(f"search_arxiv: query={query}, year_from={year_from}")
            result = self.arxiv.search(query, year_from, max_results)
            return {**result, "error": None}
        except LiteratureToolsError as e:
            logger.error(f"Tool error: {e} (retriable={e.is_retriable})")
            return {
                "papers": [],
                "error": str(e),
                "retriable": e.is_retriable,
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "papers": [],
                "error": str(e),
                "retriable": False,
            }

    def get_semantic_scholar_paper(
        self,
        paper_id_or_title: str,
        include_references: bool = True,
        include_citations: bool = True,
    ) -> Dict[str, Any]:
        """
        Fetch paper metadata from Semantic Scholar.
        
        Args:
            paper_id_or_title: Paper ID or title
            include_references: Include referenced papers
            include_citations: Include citing papers
        
        Returns:
            dict with paper metadata
        """
        try:
            logger.info(f"get_semantic_scholar_paper: {paper_id_or_title}")
            result = self.semantic_scholar.get_paper(
                paper_id_or_title,
                include_references,
                include_citations,
            )
            return {**result, "error": None}
        except LiteratureToolsError as e:
            logger.error(f"Tool error: {e} (retriable={e.is_retriable})")
            return {
                "paper": None,
                "references": [],
                "citations": [],
                "error": str(e),
                "retriable": e.is_retriable,
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "paper": None,
                "references": [],
                "citations": [],
                "error": str(e),
                "retriable": False,
            }

    def deduplicate_papers(self, papers: list) -> Dict[str, Any]:
        """
        Deduplicate and merge paper records.
        
        Args:
            papers: List of paper dictionaries
        
        Returns:
            dict with deduplicated papers and duplicate groups
        """
        try:
            logger.info(f"deduplicate_papers: {len(papers)} input papers")
            result = self.deduplicator.deduplicate(papers)
            return {**result, "error": None}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {
                "papers": papers,
                "duplicate_groups": [],
                "error": str(e),
            }

    def get_tools(self) -> list:
        """Return tool definitions for agent consumption."""
        return [
            {
                "name": "search_arxiv",
                "description": (
                    "Search the arXiv API for academic papers. Returns paper metadata "
                    "including title, authors, year, abstract, DOI, and arXiv ID. "
                    "Respects the year_from constraint to filter by publication year. "
                    "Responses are cached by request parameters to minimize API calls."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string, e.g. 'retrieval augmented generation'",
                        },
                        "year_from": {
                            "type": ["integer", "null"],
                            "description": "Optional minimum publication year filter",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default 10, max 100)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_semantic_scholar_paper",
                "description": (
                    "Fetch detailed paper metadata from Semantic Scholar, including "
                    "citations and references. Accepts a paper ID (arXiv, DOI, S2 ID) "
                    "or a title for search-based lookup."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "paper_id_or_title": {
                            "type": "string",
                            "description": "Paper ID (arXiv, DOI, S2 ID) or paper title",
                        },
                        "include_references": {
                            "type": "boolean",
                            "description": "Include papers referenced by this paper (default true)",
                            "default": True,
                        },
                        "include_citations": {
                            "type": "boolean",
                            "description": "Include papers that cite this paper (default true)",
                            "default": True,
                        },
                    },
                    "required": ["paper_id_or_title"],
                },
            },
            {
                "name": "deduplicate_papers",
                "description": (
                    "Deduplicate and merge paper records based on DOI, arXiv ID, and "
                    "normalized title. Returns a cleaned list and identifies duplicates."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "papers": {
                            "type": "array",
                            "description": "List of paper records to deduplicate",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "paper_id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "arxiv_id": {"type": ["string", "null"]},
                                    "doi": {"type": ["string", "null"]},
                                },
                            },
                        }
                    },
                    "required": ["papers"],
                },
            },
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool by name with arguments.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as dict
        
        Returns:
            Tool result as dict
        """
        if tool_name == "search_arxiv":
            return self.search_arxiv(**arguments)
        elif tool_name == "get_semantic_scholar_paper":
            return self.get_semantic_scholar_paper(**arguments)
        elif tool_name == "deduplicate_papers":
            return self.deduplicate_papers(**arguments)
        else:
            return {
                "error": f"Unknown tool: {tool_name}",
                "retriable": False,
            }

    def run_stdio(self) -> None:
        """Run as MCP server over stdio (stub for future MCP integration)."""
        logger.info("MCP stdio transport not yet implemented")
        logger.info("Use call_tool() method directly from agent")

    def run(self) -> None:
        """Alias for run_stdio()."""
        self.run_stdio()

