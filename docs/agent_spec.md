# Agent Specification

## Target User and Scenario

The target user is a student or researcher who needs a citation-grounded answer to a
scientific literature question. The agent must use public literature APIs rather than
memory-only answers.

## Inputs

- Natural-language research question.
- Optional constraints: year range, number of papers, seed paper, claim, venue, author.

## Outputs

- Structured final answer.
- Paper identifiers for every cited paper: DOI, arXiv id, Semantic Scholar id, or
  OpenAlex id when available.
- Evidence notes that connect claims to retrieved papers.
- Refusal or escalation when the agent cannot ground the answer.

## Tools

Custom MCP server:

- `search_arxiv`: searches arXiv metadata and abstracts.
- `get_semantic_scholar_paper`: retrieves citations, references, and citation counts.
- `deduplicate_papers`: merges duplicate paper records and records duplicate groups.

Third-party MCP server:

- Recommended: filesystem MCP for local cache, notes, and trajectory artifacts.

## Stopping Criteria

- The validator confirms enough retrieved evidence for the requested task.
- A human-review interrupt is reached for ambiguity or high-risk output.
- Runtime budget is hit: max iterations, max tool calls, or wall-clock timeout.
- Non-retriable tool errors make the task impossible to complete.

## Expected Failure Modes

- Top-ranked search result is not actually about the requested topic.
- DOI or arXiv id missing from one source and present in another.
- Semantic Scholar or OpenAlex rate limits.
- Ambiguous paper title maps to several papers.
- Claim asks for support even though literature mostly contradicts it.
- Model attempts to cite a paper not retrieved through tools.

## Successful Trajectory

A successful trajectory contains:

- A compact plan matching the task type.
- Relevant tool calls with valid schemas.
- Cross-checking when identifiers or citation counts disagree.
- No final citation that is absent from tool results.
- A final answer that clearly distinguishes supports, contradicts, qualifies, and unknown.

