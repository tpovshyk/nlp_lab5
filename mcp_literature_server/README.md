# Custom MCP Server for Track A Literature Research Agent

This directory implements a standalone MCP (Model Context Protocol) server that exposes literature data tools for the research agent. The server runs as a separate process and communicates with the agent via stdio transport.

## Tools Exposed

### 1. `search_arxiv`
Search the arXiv API for academic papers.

**Arguments:**
- `query` (string, required): Search query string (e.g., "retrieval augmented generation")
- `year_from` (integer, optional): Minimum publication year filter
- `max_results` (integer, default 10): Maximum number of results (max 100)

**Returns:**
- `papers`: List of paper records with metadata (title, authors, year, abstract, DOI, arXiv ID)
- `cached`: Boolean indicating whether result came from cache

**Error Handling:**
- Returns `is_retriable: true` for network errors or rate limits (HTTP 429)
- Returns `is_retriable: false` for invalid queries or parsing errors

### 2. `get_semantic_scholar_paper`
Fetch detailed paper metadata from Semantic Scholar API, including citations and references.

**Arguments:**
- `paper_id_or_title` (string, required): Paper ID (arXiv, DOI, S2 ID) or title
- `include_references` (boolean, default true): Include papers referenced by this paper
- `include_citations` (boolean, default true): Include papers that cite this paper

**Returns:**
- `paper`: Full paper metadata including citation count, venue, external IDs
- `references`: List of cited papers (up to 20)
- `citations`: List of citing papers (up to 20)
- `cached`: Boolean indicating whether result came from cache

**Error Handling:**
- Returns `is_retriable: true` for transient network failures or rate limits
- Returns `is_retriable: false` for paper not found or API parsing errors

### 3. `deduplicate_papers`
Deduplicate and merge paper records based on DOI, arXiv ID, and normalized title.

**Arguments:**
- `papers` (array, required): List of paper records to deduplicate

**Returns:**
- `papers`: Deduplicated list of unique papers
- `duplicate_groups`: List of duplicate ID groups detected

## Installation and Setup

### Prerequisites
```bash
pip install -e ".[mcp]"
```

See `pyproject.toml` for MCP dependencies.

### Running the Server

Start as a subprocess (for the agent):
```bash
python -m mcp.server
```

Or programmatically:
```python
from mcp.server import ResearchAgentServer

server = ResearchAgentServer(cache_dir=".cache")
server.run()
```

The server listens on stdio and logs to stderr (keeping stdout clean for MCP protocol messages).

## Caching Strategy

All API responses are cached by **request parameters**, not by task ID. This ensures:
- Identical requests from different tasks reuse cache
- Different tasks can still hit cache during evaluation
- The cache is safe for batch evaluation

Cache is stored in an SQLite database at `.cache/api_cache.db`.

### Cache Structure
```
cache
├── request_hash (SHA256 of request parameters)
├── api_source (e.g., "arxiv", "semantic_scholar")
├── request_key (full JSON representation)
└── response (cached API response)
```

To clear cache:
```python
from mcp.cache import RequestCache
cache = RequestCache(".cache")
cache.clear()
```

To inspect cache stats:
```python
stats = cache.stats()
print(stats)
# Output: {'total_entries': 145, 'by_source': {'arxiv': 89, 'semantic_scholar': 56}}
```

## Error Handling

Tools distinguish between **retriable** and **non-retriable** errors:

### Retriable Errors (safe to retry)
- Network timeouts or connection failures
- HTTP 429 (rate limit exceeded)
- Temporary service unavailability

### Non-Retriable Errors (retry won't help)
- Invalid API request parameters
- Paper not found (404)
- Parsing errors on valid responses
- Permission denied

The agent's graph routing layer should use these flags to decide whether to retry with exponential backoff or escalate to human review.

## File Structure

```
mcp/
├── server.py                 # MCP server main entry point
├── cache.py                  # Request-based caching layer (SQLite)
├── literature_tools.py       # Tool implementations (ArxivSearcher, SemanticScholarClient, etc.)
├── requirements-mcp.txt      # Optional: explicit MCP dependencies
└── README.md                 # This file
```

## Design Notes

### Rate Limiting
- ArXiv: 0.5 second delay between requests
- Semantic Scholar: 1 second delay between requests
- Respects published API terms of service

### Paper Deduplication
Detects duplicates by:
1. Exact DOI match (case-insensitive)
2. Exact arXiv ID match
3. Normalized title match (case-insensitive, no punctuation)

Merges metadata from all sources, keeping the first occurrence as canonical.

### Scalability
For large evaluation runs:
- Pre-populate cache with common queries
- Use `RequestCache.stats()` to monitor cache hit rate
- Run cache warmup pass before evaluation

Example warmup:
```python
common_queries = ["retrieval augmented generation", "transformer", "BERT"]
for query in common_queries:
    arxiv.search(query, max_results=20)  # Populates cache
```

