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

    def _extract_n(question: str, default: int = 5) -> int:
        """Pick the first small integer in the prompt as the requested count.

        Skips 4-digit year-like numbers; defaults to 5 when nothing matches.
        Works for both "Find the 5 most cited..." and "топ-3 статей..." style.
        """
        for m in re.findall(r"\b(\d{1,2})\b", question):
            n = int(m)
            if 1 <= n <= 50:
                return n
        return default
    
    logger = logging.getLogger(__name__)
    
    budgets = state.get("budgets", BudgetState())
    budgets.iteration_count += 1
    
    task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
    user_question = state["user_question"]
    papers = state.get("papers", [])
    tool_calls = state.get("tool_calls", [])
    requested_n = state.get("requested_n") or _extract_n(user_question)

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

            # Over-fetch (~3x) so dedup + future ranking has headroom; cap at 30.
            fetch_n = min(max(requested_n * 3, 10), 30)
            logger.info(
                f"Searching arXiv for: {query} (year_from={year_from}, "
                f"requested_n={requested_n}, fetch_n={fetch_n})"
            )
            result = mcp_server.search_arxiv(query=query, year_from=year_from, max_results=fetch_n)
            
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

        # Best-effort citation-count enrichment via Semantic Scholar. We use
        # the batch endpoint so a whole ranking lookup is ONE HTTP call - the
        # per-paper loop hammers anonymous S2 quotas and easily blows past the
        # wall-clock budget. If this fails we just keep arXiv-relevance order.
        if (
            task_type in (ResearchTaskType.MOST_CITED, ResearchTaskType.LITERATURE_REVIEW)
            and papers
        ):
            enrich_cap = min(len(papers), max(requested_n * 2, 6))
            id_to_paper: dict[str, dict] = {}
            for paper in papers[:enrich_cap]:
                arxiv_id = paper.get("arxiv_id") or paper.get("paper_id") or ""
                if not arxiv_id or paper.get("citation_count") is not None:
                    continue
                bare = re.sub(r"v\d+$", "", arxiv_id)
                id_to_paper[f"arXiv:{bare}"] = paper

            if id_to_paper:
                logger.info(
                    f"Enriching {len(id_to_paper)} papers via S2 batch endpoint"
                )
                batch_result = mcp_server.get_semantic_scholar_papers_batch(
                    ids=list(id_to_paper.keys()),
                )
                tool_calls.append({
                    "tool": "get_semantic_scholar_papers_batch",
                    "args": {"ids": list(id_to_paper.keys()), "purpose": "citation_count"},
                    "result": batch_result,
                })
                for s2_paper, queried_id in zip(
                    batch_result.get("papers") or [], id_to_paper.keys()
                ):
                    if not isinstance(s2_paper, dict):
                        continue
                    cc = s2_paper.get("citationCount")
                    if cc is not None:
                        id_to_paper[queried_id]["citation_count"] = cc

                # Re-rank with whatever citation data we got. Papers still
                # missing a count slot to the bottom but stay in the pool.
                papers = sorted(
                    papers,
                    key=lambda p: (
                        p.get("citation_count")
                        if p.get("citation_count") is not None else -1
                    ),
                    reverse=True,
                )
                top_cc = [p.get("citation_count") for p in papers[:5]]
                logger.info(f"After citation enrichment, top citation_counts={top_cc}")

        logger.info(f"Search complete: {len(papers)} papers found, {len(tool_calls)} tool calls made")
        
        return {
            **state,
            "budgets": budgets,
            "papers": papers,
            "tool_calls": tool_calls,
            "requested_n": requested_n,
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
    tool_calls = state.get("tool_calls", [])

    # If the last search round only produced retriable tool errors and no papers,
    # don't keep looping - bail out so write_answer can render a useful message.
    last_round_errors = [
        tc.get("result", {}).get("error")
        for tc in tool_calls
        if isinstance(tc.get("result"), dict) and tc.get("result", {}).get("error")
    ]
    only_errors = bool(last_round_errors) and not papers

    validation = ValidationReport(
        enough_evidence=bool(papers),
        needs_human_review=(
            state.get("task_type") == ResearchTaskType.UNKNOWN or only_errors
        ),
        notes=last_round_errors if only_errors else (
            [] if papers else ["No retrieved papers yet."]
        ),
    )
    return {**state, "validation": validation}


_WRITER_INSTRUCTIONS = {
    ResearchTaskType.MOST_CITED: (
        "Produce a ranked list (1, 2, 3, ...) of the {n} most-cited papers from "
        "the list. For each: title (bold), authors (first 3 + 'et al.' if more), "
        "year, identifier (arXiv id or DOI), citation count if known, and a "
        "ONE-sentence summary distilled from the abstract."
    ),
    ResearchTaskType.CLAIM_EVIDENCE: (
        "Group papers under headings 'Supporting:', 'Contradicting:', and "
        "'Background:' based on what their abstracts indicate about the user's "
        "claim. For each paper give title, identifier, and a one-sentence "
        "justification for the placement. If a paper's abstract is ambiguous "
        "put it under 'Background'."
    ),
    ResearchTaskType.PAPER_COMPARISON: (
        "Compare the papers across (a) what they propose, (b) datasets/benchmarks, "
        "(c) reported results, (d) main difference. Conclude with a short verdict "
        "on when to prefer each. Always cite each paper by identifier."
    ),
    ResearchTaskType.LITERATURE_REVIEW: (
        "Write a 2-3 paragraph literature review citing each paper at least once "
        "by identifier. Group by sub-theme where reasonable. End with one sentence "
        "on open problems."
    ),
}


def _format_papers_for_prompt(papers: list[dict]) -> str:
    rows = []
    for i, p in enumerate(papers, 1):
        ident = p.get("arxiv_id") or p.get("doi") or p.get("paper_id") or "?"
        authors = p.get("authors", []) or []
        authors_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        cc = p.get("citation_count")
        cc_str = f"  citations={cc}" if cc is not None else ""
        abstract = (p.get("abstract") or "").strip().replace("\n", " ")[:400]
        rows.append(
            f"[{i}] id={ident}  year={p.get('year', '?')}{cc_str}\n"
            f"    title: {p.get('title', '')}\n"
            f"    authors: {authors_str or 'Unknown'}\n"
            f"    abstract: {abstract}"
        )
    return "\n\n".join(rows)


def _llm_write_answer(state: AgentState, papers: list[dict]) -> str | None:
    """Synthesize the final answer with the configured LLM. Returns None on failure."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        llm = _build_classifier_llm()
        task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
        instr = _WRITER_INSTRUCTIONS.get(
            task_type,
            "Produce a ranked list of the relevant papers with title, "
            "identifier, year, and a one-sentence summary each.",
        ).format(n=state.get("requested_n") or len(papers))

        retrieved_ids = sorted({
            (p.get("arxiv_id") or p.get("doi") or p.get("paper_id") or "")
            for p in papers if p.get("arxiv_id") or p.get("doi") or p.get("paper_id")
        })

        prompt = (
            "You are a careful research assistant. Answer the user's question "
            "using ONLY the papers listed below. Never invent identifiers, "
            "citation counts, or authors. If a fact isn't in the list, omit it.\n\n"
            f"User question: {state.get('user_question', '')}\n\n"
            f"Task type: {task_type}\n\n"
            f"Format instructions:\n{instr}\n\n"
            "Output rules:\n"
            "- Use Telegram-style legacy Markdown (**bold**, _italic_).\n"
            "- Cite a paper by writing its arXiv id or DOI in parentheses right "
            "after the title.\n"
            "- Allowed identifiers (DO NOT use any other): "
            f"{retrieved_ids}\n"
            "- Keep the response under 3000 characters.\n"
            "- Avoid characters that would break Markdown parsing inside titles "
            "(escape stray '_' / '*' / '[' / '`' with a backslash).\n\n"
            f"Papers:\n{_format_papers_for_prompt(papers)}\n\n"
            "Answer:"
        )

        response = llm.invoke(prompt)
        content = getattr(response, "content", None)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        if not content or not str(content).strip():
            return None
        return str(content).strip()
    except Exception as exc:
        logger.warning(f"LLM write_answer failed, falling back to static format: {exc}")
        return None


def write_answer(state: AgentState) -> AgentState:
    """Produce the final answer from validated evidence only."""

    import re

    papers = state.get("papers", [])
    if not papers:
        tool_calls = state.get("tool_calls", [])
        retriable_errors: list[str] = []
        non_retriable_errors: list[str] = []
        for tc in tool_calls:
            res = tc.get("result") if isinstance(tc, dict) else None
            if not isinstance(res, dict) or not res.get("error"):
                continue
            line = f"- {tc.get('tool', 'tool')}: {res['error']}"
            if res.get("retriable"):
                retriable_errors.append(line)
            else:
                non_retriable_errors.append(line)

        if retriable_errors and not non_retriable_errors:
            msg = (
                "The literature APIs are rate-limiting or timing out right now. "
                "Please wait a minute and retry the same query; cached queries will "
                "still work.\n\n" + "\n".join(retriable_errors)
            )
        elif retriable_errors or non_retriable_errors:
            msg = (
                "I could not retrieve papers because the literature search tool "
                "failed.\n\n" + "\n".join(retriable_errors + non_retriable_errors)
            )
        else:
            msg = "No papers were retrieved for your query."
        return {**state, "final_answer": msg}

    task_type = state.get("task_type", ResearchTaskType.UNKNOWN)
    user_question = state.get("user_question", "")
    requested_n = state.get("requested_n")

    # Sort by citation_count descending where available
    sorted_papers = sorted(
        papers,
        key=lambda p: (p.get("citation_count") or 0) if isinstance(p, dict) else (p.citation_count or 0),
        reverse=True,
    )

    # Trim to the user's requested count for ranked tasks (most_cited, etc.)
    if requested_n and task_type in (
        ResearchTaskType.MOST_CITED,
        ResearchTaskType.LITERATURE_REVIEW,
    ):
        sorted_papers = sorted_papers[:requested_n]

    # Try LLM-driven synthesis first; fall back to the static formatter if it
    # fails, returns nothing, or the configured LLM is unavailable.
    llm_answer = _llm_write_answer(state, sorted_papers)
    if llm_answer:
        return {**state, "final_answer": llm_answer}

    def _md_escape(value: object) -> str:
        """Escape Telegram legacy-Markdown special characters in dynamic text.

        Telegram chokes on lone `_`/`*`/`[`/`` ` `` in titles, author names with
        formula fragments, DOIs containing `(`/`)`, etc. The four chars below
        are the ones the legacy parser treats as entity starters.
        """
        return re.sub(r"([_*\[`])", r"\\\1", str(value))

    safe_q = _md_escape(user_question)
    lines = [f"🔬 **Research Results**\n\nQuery: _{safe_q}_\n"]
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

        entry = f"**{i}. {_md_escape(title)}**\n"
        entry += f"   Authors: {_md_escape(author_str)}\n"
        entry += f"   Year: {_md_escape(year)}\n"
        if arxiv_id:
            entry += f"   arXiv: {_md_escape(arxiv_id)}\n"
        if doi:
            entry += f"   DOI: {_md_escape(doi)}\n"
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

