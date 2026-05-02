# MCP Server Implementation Summary

## ✅ Completed

### 1. Request-Based Caching (`mcp/cache.py`)
- SQLite-backed cache keyed by **request parameters**, not task ID
- Deterministic SHA256 hashing of request dict ensures cache hits across tasks
- `RequestCache` class with `get()`, `set()`, `clear()`, `stats()` methods
- Cache survives process restart
- Stats show per-source breakdown (arXiv vs Semantic Scholar hits)

**Key Methods:**
```python
cache = RequestCache(".cache")
cached = cache.get("arxiv", {"query": "transformers", "year_from": 2020})
cache.set("arxiv", request_params, response)
print(cache.stats())  # {'total_entries': 45, 'by_source': {'arxiv': 30, 's2': 15}}
```

### 2. Literature Tools (`mcp/literature_tools.py`)

#### ArxivSearcher
- Searches arXiv Atom API
- Parses XML, extracts: title, authors, year, abstract, DOI, arXiv ID
- Rate limit: 0.5s between requests (respects arXiv ToS)
- Caches responses by request
- Error handling: distinguishes rate-limit (429) as retriable

```python
searcher = ArxivSearcher(cache)
result = searcher.search("retrieval augmented generation", year_from=2020, max_results=10)
# Returns: {"papers": [...], "cached": False}
```

#### SemanticScholarClient
- Fetches paper metadata from Semantic Scholar API
- Accepts paper ID (arXiv, DOI, S2 ID) or title-based lookup
- Fetches citations and references (limited to 20 each)
- Rate limit: 1s between requests
- Error handling: returns None for 404, raises on 429

```python
client = SemanticScholarClient(cache)
result = client.get_paper("2020.12345", include_references=True, include_citations=True)
# Returns: {"paper": {...}, "references": [...], "citations": [...], "cached": False}
```

#### PaperDeduplicator
- Detects duplicates by:
  1. Exact DOI match (case-insensitive)
  2. Exact arXiv ID match
  3. Normalized title (lowercase, no punctuation)
- Merges metadata, keeps first occurrence as canonical
- Returns unique papers + duplicate groups

```python
dedup = PaperDeduplicator(cache)
result = dedup.deduplicate(papers)
# Returns: {"papers": [...], "duplicate_groups": [["id1", "id2"], ...]}
```

#### Error Handling
- All tools raise `LiteratureToolsError` with `is_retriable` flag
- Retriable: network errors, rate limits (HTTP 429), timeouts
- Non-retriable: invalid query, paper not found, parsing errors

### 3. MCP Server (`mcp/server.py`)
- Implements MCP protocol over stdio transport
- Registers 3 tools: `search_arxiv`, `get_semantic_scholar_paper`, `deduplicate_papers`
- Each tool has:
  - Full JSON schema for arguments
  - Descriptive tool description (shown to LLM)
  - Error handling with `is_retriable` flag
- Logs to stderr (keeps stdout clean for MCP protocol)
- Entry point: `python -m mcp --cache-dir .cache`

**Tool Discovery:**
```python
server = ResearchAgentServer()
tools = server.get_tools()
# Returns list of 3 tools with name, description, inputSchema
```

### 4. Tests (`tests/test_literature_tools.py`)
**12 tests, all passing:**
- ✅ Cache set/get
- ✅ Cache keying by request (not task)
- ✅ Cache stats
- ✅ ArxivSearcher init and cache hit
- ✅ Dedupe by DOI
- ✅ Dedupe by arXiv ID
- ✅ Dedupe by normalized title
- ✅ No duplicates (unique papers preserved)
- ✅ Empty list handling
- ✅ Retriable vs non-retriable error flags

Run tests:
```bash
source .venv/bin/activate
python -m pytest tests/test_literature_tools.py -v
```

### 5. Documentation
- **`mcp/README.md`** — Full tool contracts, caching strategy, rate limits, error handling
- **`mcp/INTEGRATION.md`** — Step-by-step guide to connect server to LangGraph agent
  - Pattern 1: LangChain Tool wrappers
  - Pattern 2: Direct MCP calls in node
  - Error handling in agent
  - Testing patterns
  - Deployment scenarios
  - Debugging tips

- **`docs/handoff.md`** — Updated with completion status and next steps

## 📦 Deliverables

### Files Created/Modified

```
mcp/
├── __init__.py                  # Package init
├── __main__.py                  # Entry point for `python -m mcp`
├── cache.py                     # Request-based SQLite caching (310 lines)
├── literature_tools.py          # ArxivSearcher, SemanticScholarClient, PaperDeduplicator (400+ lines)
├── server.py                    # MCP server with 3 tools (280+ lines)
├── README.md                    # Tool contracts & usage (updated)
├── INTEGRATION.md               # Agent integration guide (new, 300+ lines)
└── .cache/
    └── api_cache.db            # SQLite cache (created on first run)

tests/
└── test_literature_tools.py     # 12 tests, all passing

docs/
└── handoff.md                   # Updated status & timeline

pyproject.toml                   # Updated with [mcp] dependencies
```

### Dependencies Added
- `mcp>=0.5.0` — Model Context Protocol
- `requests>=2.31.0` — HTTP library for API calls

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd /Users/mac/nlp_lab5
source .venv/bin/activate
pip install -e ".[mcp,dev]"
```

### 2. Start the MCP Server
```bash
python -m mcp --cache-dir /tmp/cache
```

Expected output (logs to stderr):
```
2024-05-02 14:30:45 - root - INFO - Starting Research Agent MCP Server
2024-05-02 14:30:45 - root - INFO - Cache directory: /tmp/cache
2024-05-02 14:30:45 - root - INFO - Available tools: ['search_arxiv', 'get_semantic_scholar_paper', 'deduplicate_papers']
```

### 3. Test Tools (manually)
```bash
# In Python REPL
import sys
sys.path.insert(0, "mcp")
from cache import RequestCache
from literature_tools import ArxivSearcher

cache = RequestCache()
searcher = ArxivSearcher(cache)
result = searcher.search("transformers", max_results=5)
print(f"Found {len(result['papers'])} papers")
```

### 4. Run Tests
```bash
python -m pytest tests/test_literature_tools.py -v
```

## 🔌 Connecting to Agent (Next Steps)

See `mcp/INTEGRATION.md` for detailed patterns. Quick example:

```python
# In graph.py or search_papers node
from mcp.server import ResearchAgentServer
import asyncio

async def search_papers(state: AgentState) -> AgentState:
    server = ResearchAgentServer()
    tools = server.get_tools()
    
    # Search arXiv for papers matching the question
    question = state["user_question"]
    result = await call_tool("search_arxiv", {
        "query": question,
        "max_results": 10
    })
    
    papers = result["papers"]
    
    # Deduplicate if needed
    if state.get("papers"):
        all_papers = state["papers"] + papers
        result = await call_tool("deduplicate_papers", {"papers": all_papers})
        papers = result["papers"]
    
    return {
        **state,
        "papers": papers,
        "tool_calls": [...],
    }
```

## 📊 Caching Strategy Verification

The cache is **request-based**, not task-based:

```python
# Scenario: Two different tasks ask similar questions
task1 = {"user_question": "Find papers on transformers after 2020"}
task2 = {"user_question": "Find papers on attention mechanisms after 2020"}

# Task 1 searches for "transformers"
cache.set("arxiv", {"query": "transformers", "year_from": 2020}, result1)

# Task 2 searches for "attention mechanisms" (different query)
# → Cache miss (different query), calls API again

# Later, Task 3 searches for "transformers" again
# → Cache hit! Reuses result1 (identical query)
```

This ensures:
- ✅ Evaluation runs benefit from caching (repeated queries hit cache)
- ✅ No hardcoding (cache key = API request, not task ID)
- ✅ Safe for batch evaluation

## ⚠️ Compliance Notes

### API Rate Limits
- **ArXiv**: 0.5s delay between requests (hardcoded in `ArxivSearcher`)
- **Semantic Scholar**: 1s delay between requests (hardcoded in `SemanticScholarClient`)
- Both respect published API terms of service

### Cache Safety
- Cache is not assumed to be warm
- First evaluation run will hit APIs (then cache for subsequent runs)
- During demo, Lecturer may test with cold cache
- Provide cached trajectories as fallback

### Error Handling
- Retriable errors (429, timeout): agent should retry with backoff
- Non-retriable errors (404, invalid params): agent should escalate or skip
- Both include error message + `is_retriable` flag

## 📝 Next Steps (Not in This PR)

1. **Wire MCP into agent nodes** (Participant 3)
   - `search_papers` node calls tools
   - `validate_evidence` node checks citations are grounded
   - `write_answer` node produces final output

2. **Create evaluation set** (Participant 3)
   - 30+ tasks in `eval/tasks.json`
   - Each with rubric + expected behaviors
   - Include adversarial cases (should refuse/escalate)

3. **Collect trajectories** (Participant 3)
   - Run agent on all tasks
   - Save per-step: inputs, tool calls, outputs, tokens, latency
   - Machine-readable format (JSON/CSV)

4. **Run ablations** (Participant 3)
   - Model ablation: Claude vs GPT-4
   - Prompt ablation: different system prompt
   - Graph ablation: skip validator or change structure

5. **Write report** (Participant 3)
   - Agent spec + diagram
   - Tool contracts
   - Eval set + rubrics
   - Aggregate metrics
   - Failure traces
   - Ablation results

## 🔍 Debugging Checklist

- [ ] MCP server starts without errors
- [ ] All 3 tools appear in `server.get_tools()`
- [ ] Cache creates SQLite DB at specified path
- [ ] Test tools with live queries (arXiv, Semantic Scholar)
- [ ] Verify cache hits on repeated queries
- [ ] Test retriable error (rate limit) recovery
- [ ] Verify non-retriable errors don't retry
- [ ] All 12 tests pass

## 📞 Support

For questions on MCP integration, see:
- `mcp/README.md` — Tool contracts and caching
- `mcp/INTEGRATION.md` — Agent connection patterns
- `tests/test_literature_tools.py` — Example usage
- `mcp/server.py` — Tool implementations
