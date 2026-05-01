# Custom MCP Server Handoff

The server must run as a separate process during the demo and expose at least three
Track A tools. See `src/research_agent/tool_contracts.py` for the current expected
schemas.

Suggested tools:

- `search_arxiv`
- `get_semantic_scholar_paper`
- `deduplicate_papers`

Optional but useful:

- `search_openalex`
- `get_common_references`
- `write_research_note`

