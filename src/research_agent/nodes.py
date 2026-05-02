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


_CLASSIFY_PROMPTS = {
    "default": (
        "Analyze this research question and classify it into one of these task types:\n\n"
        "1. most_cited: \"Find the N most-cited papers on [topic]\"\n"
        "2. claim_evidence: \"Find papers that support/contradict [claim]\"\n"
        "3. paper_comparison: \"Compare papers X and Y\" or \"Papers that cite/are cited by X\"\n"
        "4. literature_review: \"Give a literature review on [topic]\"\n"
        "5. unknown: Doesn't fit the above categories\n\n"
        "User's question: \"{question}\"\n\n"
        "Respond with the task type and brief reasoning."
    ),
    "minimal": (
        "Pick one label for this query: most_cited | claim_evidence | "
        "paper_comparison | literature_review | unknown.\n"
        "Query: {question}"
    ),
    "verbose": (
        "You are a careful research-librarian classifier. The agent downstream will "
        "use the label to pick tools, so a wrong label costs API calls and time.\n\n"
        "Labels (and what they imply):\n"
        "- most_cited: user wants ranked papers; cite counts matter; arXiv + Semantic Scholar.\n"
        "- claim_evidence: user gave a claim; agent must find supporting OR contradicting papers.\n"
        "- paper_comparison: user named >=2 specific papers; agent should fetch metadata for each.\n"
        "- literature_review: user wants synthesis over a topic, multiple papers, possibly recent.\n"
        "- unknown: ambiguous, underspecified, or out-of-scope; downstream may need clarification.\n\n"
        "Be conservative: if specific papers are not named, do NOT pick paper_comparison; "
        "if no claim is stated, do NOT pick claim_evidence.\n\n"
        "Question: \"{question}\"\n"
        "Return the label and a one-sentence reason."
    ),
}


def _build_classifier_llm():
    """Instantiate the classifier LLM, honoring MODEL_PROVIDER and MODEL_NAME envs."""

    import os

    provider = os.getenv("MODEL_PROVIDER", "anthropic").lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model_name = os.getenv("MODEL_NAME", "claude-haiku-4-5-20251001")
        return ChatAnthropic(model=model_name)
    if provider == "openai":
        from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
        model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
        return ChatOpenAI(model=model_name)
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import-not-found]
        model_name = os.getenv("MODEL_NAME", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(model=model_name)
    raise ValueError(f"Unsupported MODEL_PROVIDER: {provider}")


def classify_task(state: AgentState) -> AgentState:
    """Classify the research question into a Track A task family.

    Replace this heuristic with an LLM structured-output call in the real graph.
    """

    import os
    import logging
    from pydantic import BaseModel, Field
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    logger = logging.getLogger(__name__)

    class TaskClassification(BaseModel):
        """Classification result from Claude."""
        task_type: str = Field(
            description="One of: most_cited, claim_evidence, paper_comparison, literature_review, unknown"
        )
        reasoning: str = Field(description="Brief reasoning for the classification")

    try:
        llm = _build_classifier_llm()

        # Create structured output LLM
        structured_llm = llm.with_structured_output(TaskClassification)

        # Create classification prompt (variant configurable for ablation)
        variant = os.getenv("CLASSIFY_PROMPT_VARIANT", "default")
        template = _CLASSIFY_PROMPTS.get(variant, _CLASSIFY_PROMPTS["default"])
        prompt = template.format(question=state["user_question"])
        
        # Call Claude
        result = structured_llm.invoke(prompt)
        
        # Map string to enum
        task_type_str = result.task_type.lower().replace(" ", "_")
        try:
            task_type = ResearchTaskType(task_type_str)
        except ValueError:
            task_type = ResearchTaskType.UNKNOWN
        
        logger.info(f"Classified task as: {task_type} ({result.reasoning})")
        
        return {
            **state,
            "task_type": task_type,
            "transient_notes": [
                *state.get("transient_notes", []),
                f"Classification: {task_type} - {result.reasoning}"
            ]
        }
    
    except Exception as e:
        logger.error(f"Error in classify_task: {e}")
        # Fall back to heuristic
        question = state["user_question"].lower()
        if "most-cited" in question or "most cited" in question:
            task_type = ResearchTaskType.MOST_CITED
        elif "support" in question or "contradict" in question:
            task_type = ResearchTaskType.CLAIM_EVIDENCE
        elif "compare" in question:
            task_type = ResearchTaskType.PAPER_COMPARISON
        elif "literature" in question and "review" in question:
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

    import logging
    import re
    import sys
    from pathlib import Path

    # Add parent directory to path to import mcp_literature_server as package
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from mcp_literature_server.research_server import ResearchAgentServer

    def _extract_topic(question: str) -> str:
        """Strip filler words to get a clean arXiv search query."""
        filler = re.compile(
            r"^(find|give|show|get|list|compare|top\s+\d+\s+|"
            r"(\d+\s+)?most[-\s]cited\s+papers?\s+on\s+|"
            r"cited\s+papers?\s+on\s+|"
            r"papers?\s+(on|about|that|for|supporting|contradicting)\s+|"
            r"literature\s+review\s+on\s+|after\s+\d{4}\s*)",
            re.IGNORECASE,
        )
        q = question.strip()
        prev = None
        while prev != q:
            prev = q
            q = filler.sub("", q).strip()
        # Also strip trailing year phrases
        q = re.sub(r"\s+after\s+\d{4}$", "", q, flags=re.IGNORECASE).strip()
        return q or question
    
    logger = logging.getLogger(__name__)
    
    budgets = state.get("budgets", BudgetState())
    budgets.iteration_count += 1
    
    task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
    user_question = state["user_question"]
    papers = state.get("papers", [])
    tool_calls = state.get("tool_calls", [])
    
    try:
        # Initialize MCP server
        mcp_server = ResearchAgentServer()
        logger.info(f"MCP server initialized for task type: {task_type}")
        
        # Strategy depends on task type
        if task_type == ResearchTaskType.MOST_CITED:
            # Extract topic and year from question
            query = _extract_topic(user_question)
            year_from = None
            if "after" in user_question.lower():
                years = re.findall(r'\d{4}', user_question)
                if years:
                    year_from = int(years[-1])
            
            logger.info(f"Searching arXiv for: {query} (year_from={year_from})")
            result = mcp_server.search_arxiv(query=query, year_from=year_from, max_results=20)
            
            tool_calls.append({
                "tool": "search_arxiv",
                "args": {"query": query, "year_from": year_from},
                "result": result
            })
            
            if result.get("papers"):
                papers = result["papers"]
                logger.info(f"Found {len(papers)} papers on arXiv")
        
        elif task_type == ResearchTaskType.CLAIM_EVIDENCE:
            # Search for papers supporting/contradicting a claim
            query = _extract_topic(user_question)
            logger.info(f"Searching for evidence: {query}")
            result = mcp_server.search_arxiv(query=query, max_results=15)
            
            tool_calls.append({
                "tool": "search_arxiv",
                "args": {"query": query},
                "result": result
            })
            
            if result.get("papers"):
                papers = result["papers"]
                logger.info(f"Found {len(papers)} papers for claim evidence")
        
        elif task_type == ResearchTaskType.PAPER_COMPARISON:
            # Extract paper titles/IDs to compare
            import re
            # Try to find paper titles in quotes or mentions
            papers_to_find = re.findall(r'"([^"]+)"', user_question)
            if not papers_to_find:
                papers_to_find = re.findall(r'papers?\s+(\w+\s+\w+)', user_question)
            
            for paper_id in papers_to_find[:3]:  # Max 3 papers
                logger.info(f"Fetching paper: {paper_id}")
                result = mcp_server.get_semantic_scholar_paper(
                    paper_id_or_title=paper_id,
                    include_references=True,
                    include_citations=True
                )
                
                tool_calls.append({
                    "tool": "get_semantic_scholar_paper",
                    "args": {"paper_id_or_title": paper_id},
                    "result": result
                })
                
                if result.get("paper"):
                    papers.append(result["paper"])
        
        elif task_type == ResearchTaskType.LITERATURE_REVIEW:
            # Search for recent papers on the topic
            query = _extract_topic(user_question)
            year_from = 2020  # Recent papers
            logger.info(f"Searching literature review papers: {query} (after {year_from})")
            result = mcp_server.search_arxiv(query=query, year_from=year_from, max_results=25)
            
            tool_calls.append({
                "tool": "search_arxiv",
                "args": {"query": query, "year_from": year_from},
                "result": result
            })
            
            if result.get("papers"):
                papers = result["papers"]
                logger.info(f"Found {len(papers)} papers for literature review")
        
        else:
            # Fallback: generic arXiv search for unknown task types
            query = _extract_topic(user_question)
            logger.info(f"Fallback search for unknown task type: {query}")
            result = mcp_server.search_arxiv(query=query, max_results=10)
            tool_calls.append({"tool": "search_arxiv", "args": {"query": query}, "result": result})
            if result.get("papers"):
                papers = result["papers"]
                logger.info(f"Found {len(papers)} papers via fallback search")

        # Deduplicate papers if we have any
        if papers and len(papers) > 1:
            logger.info(f"Deduplicating {len(papers)} papers")
            dedup_result = mcp_server.deduplicate_papers(papers=papers)
            
            tool_calls.append({
                "tool": "deduplicate_papers",
                "args": {"papers": papers},
                "result": dedup_result
            })
            
            papers = dedup_result.get("papers", papers)
            logger.info(f"After deduplication: {len(papers)} unique papers")
        
        logger.info(f"Search complete: {len(papers)} papers found, {len(tool_calls)} tool calls made")
        
        return {
            **state,
            "budgets": budgets,
            "papers": papers,
            "tool_calls": tool_calls,
            "transient_notes": [
                *state.get("transient_notes", []),
                f"search_papers: Found {len(papers)} papers with {len(tool_calls)} tool calls"
            ]
        }
    
    except Exception as e:
        logger.error(f"Error in search_papers: {e}", exc_info=True)
        return {
            **state,
            "budgets": budgets,
            "transient_notes": [
                *state.get("transient_notes", []),
                f"search_papers error: {str(e)}"
            ]
        }


def validate_evidence(state: AgentState) -> AgentState:
    """Check whether the current paper/evidence set is enough."""

    papers = state.get("papers", [])
    validation = ValidationReport(
        enough_evidence=bool(papers),
        needs_human_review=state.get("task_type") == ResearchTaskType.UNKNOWN,
        notes=[] if papers else ["No retrieved papers yet."],
    )
    return {**state, "validation": validation}


def write_answer(state: AgentState) -> AgentState:
    """Produce the final answer from validated evidence only."""

    papers = state.get("papers", [])
    if not papers:
        return {**state, "final_answer": "No papers were retrieved for your query."}

    task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
    user_question = state.get("user_question", "")

    # Sort by citation_count descending where available
    sorted_papers = sorted(
        papers,
        key=lambda p: (p.get("citation_count") or 0) if isinstance(p, dict) else (p.citation_count or 0),
        reverse=True,
    )

    lines = [f"🔬 **Research Results**\n\nQuery: _{user_question}_\n"]
    for i, paper in enumerate(sorted_papers, 1):
        if isinstance(paper, dict):
            title = paper.get("title", "Unknown title")
            authors = paper.get("authors", [])
            year = paper.get("year", "?")
            arxiv_id = paper.get("arxiv_id") or paper.get("paper_id", "")
            doi = paper.get("doi", "")
            citations = paper.get("citation_count")
        else:
            title = paper.title
            authors = paper.authors
            year = paper.year or "?"
            arxiv_id = paper.arxiv_id or paper.paper_id
            doi = paper.doi or ""
            citations = paper.citation_count

        author_str = ", ".join(authors[:3]) if authors else "Unknown"
        if len(authors) > 3:
            author_str += " et al."

        entry = f"**{i}. {title}**\n"
        entry += f"   Authors: {author_str}\n"
        entry += f"   Year: {year}\n"
        if arxiv_id:
            entry += f"   arXiv: {arxiv_id}\n"
        if doi:
            entry += f"   DOI: {doi}\n"
        if citations is not None:
            entry += f"   Citations: {citations}\n"
        lines.append(entry)

    answer = "\n".join(lines)
    return {**state, "final_answer": answer}


def stop_with_budget_message(state: AgentState) -> AgentState:
    """Exit cleanly when a budget is hit."""

    budgets = state.get("budgets", BudgetState(stop_reason="unknown_budget"))
    return {
        **state,
        "final_answer": f"Stopped because budget was reached: {budgets.stop_reason}.",
    }

