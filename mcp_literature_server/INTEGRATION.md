"""Integration guide for connecting MCP server to the LangGraph agent."""

# Integration Guide: MCP Server to LangGraph Agent

This document explains how to integrate the literature MCP server with the LangGraph agent in `search_papers` node.

## Quick Start

### 1. Start the MCP Server

In a separate terminal:
```bash
cd /Users/mac/nlp_lab5
source .venv/bin/activate
python -m mcp
```

Expected output:
```
2024-05-02 14:30:45,123 - root - INFO - Starting Research Agent MCP Server
2024-05-02 14:30:45,124 - root - INFO - Cache directory: /Users/mac/nlp_lab5/mcp/.cache
2024-05-02 14:30:45,125 - root - INFO - Available tools: ['search_arxiv', 'get_semantic_scholar_paper', 'deduplicate_papers']
```

### 2. Connect Agent to MCP Server

In your LangGraph agent code (`graph.py` or in the `search_papers` node):

```python
from langchain_core.tools import Tool
from langchain_anthropic import Anthropic
import subprocess
import json

# Start MCP server
mcp_process = subprocess.Popen(
    [sys.executable, "-m", "mcp"],
    cwd="/Users/mac/nlp_lab5/mcp",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Initialize MCP client (using stdio transport)
from mcp.client.stdio import StdioClientTransport
from mcp import Client

async def connect_mcp():
    transport = StdioClientTransport(
        command=[sys.executable, "-m", "mcp"],
        cwd="/Users/mac/nlp_lab5/mcp",
    )
    async with Client(transport) as client:
        # Get available tools
        tools = await client.get_tools()
        return client, tools
```

## Tool Integration Patterns

### Pattern 1: LangChain Tool Wrappers

Create Tool objects from MCP tools:

```python
from langchain_core.tools import Tool

def search_arxiv(query: str, year_from: int = None, max_results: int = 10) -> str:
    """Search arXiv for papers."""
    result = await mcp_client.call_tool(
        "search_arxiv",
        {"query": query, "year_from": year_from, "max_results": max_results},
    )
    return json.dumps(result)

# Wrap as LangChain tool
arxiv_tool = Tool(
    name="search_arxiv",
    func=search_arxiv,
    description="Search the arXiv API for academic papers.",
)
```

### Pattern 2: Direct MCP Calls in Node

```python
async def search_papers(state: AgentState) -> AgentState:
    """Call literature MCP tools."""
    
    question = state["user_question"]
    plan = state["plan"]
    
    # Connect to MCP server
    async with mcp_client as client:
        # Search arXiv
        arxiv_result = await client.call_tool(
            "search_arxiv",
            {"query": question, "max_results": 10}
        )
        
        papers = arxiv_result["papers"]
        
        # Deduplicate if we already have results
        if state.get("papers"):
            all_papers = state["papers"] + papers
            dedupe_result = await client.call_tool(
                "deduplicate_papers",
                {"papers": all_papers}
            )
            papers = dedupe_result["papers"]
        
        # Update state
        return {
            **state,
            "papers": papers,
            "tool_calls": [
                *state.get("tool_calls", []),
                ToolCallRecord(
                    call_id=str(uuid4()),
                    tool_name="search_arxiv",
                    arguments={"query": question},
                    status="ok",
                ),
            ],
        }
```

## Error Handling in Agent

The MCP server returns errors with `is_retriable` flag. Handle in agent:

```python
def search_papers(state: AgentState) -> AgentState:
    try:
        result = arxiv_search(query)
        # Normal flow
    except ToolError as e:
        if e.is_retriable:
            # Add to retry queue
            state["transient_notes"].append(f"Retriable error, will retry: {e}")
            # Maybe sleep and retry, or request human review
        else:
            # Non-retriable error
            state["transient_notes"].append(f"Cannot retry: {e}")
            # Escalate or skip this search
    
    return state
```

## Deployment Scenarios

### Scenario A: Local Development
- MCP server runs in same machine as agent
- Use stdio transport
- Cache lives in `.cache/` directory

### Scenario B: Remote Deployment
- MCP server runs on different machine
- Use HTTP/SSE or TCP transport (requires MCP update)
- Cache should be on shared storage (NFS, S3, etc.)

### Scenario C: Docker / Container
- Package MCP server in container
- Agent container connects via network socket
- Shared volume for cache

## Testing the Integration

### 1. Unit Test: Tool Availability

```python
def test_arxiv_tool_available():
    tools = mcp_client.get_tools()
    tool_names = [t["name"] for t in tools]
    assert "search_arxiv" in tool_names
    assert "get_semantic_scholar_paper" in tool_names
    assert "deduplicate_papers" in tool_names
```

### 2. Integration Test: Agent + Server

```python
async def test_search_papers_node():
    # Start server
    mcp_process = start_mcp_server()
    
    # Run agent node
    initial_state = AgentState(
        user_question="Find papers on transformers published after 2020"
    )
    result_state = await search_papers(initial_state)
    
    # Check results
    assert len(result_state["papers"]) > 0
    assert all(p["year"] >= 2020 for p in result_state["papers"] if p["year"])
    
    # Cleanup
    mcp_process.terminate()
```

### 3. End-to-End Test: Full Graph

```python
async def test_full_agent():
    # Start server
    mcp_process = start_mcp_server()
    
    # Build and invoke agent
    graph = build_graph()
    result = await graph.ainvoke({
        "user_question": "Find 3 most-cited papers on RAG",
    })
    
    # Verify results
    assert "final_answer" in result
    assert len(result["papers"]) >= 3
    
    # Check all papers are properly attributed
    for evidence in result["evidence"]:
        assert evidence["paper_id"] in [p["paper_id"] for p in result["papers"]]
```

## Debugging Tips

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Inspect Cache

```python
from mcp.cache import RequestCache
cache = RequestCache(".cache")
print(cache.stats())
# Output: {'total_entries': 45, 'by_source': {'arxiv': 30, 'semantic_scholar': 15}}
```

### Dry-Run MCP Server

Test tools manually without agent:

```bash
# Start server in verbose mode
python -m mcp --cache-dir /tmp/test_cache

# In another terminal, send tool call via stdio:
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", ...}' | python -m mcp
```

## Performance Tuning

### Cache Warmup
Pre-populate cache for common queries:

```python
def warmup_cache():
    common_topics = [
        "retrieval augmented generation",
        "large language models",
        "transformer architecture",
    ]
    for topic in common_topics:
        arxiv.search(topic, max_results=20)
```

### Rate Limit Tuning
Adjust in `literature_tools.py`:

```python
# Reduce rate limit delay for faster execution (but respect API terms)
arxiv = ArxivSearcher(cache, rate_limit_delay=0.3)
semantic_scholar = SemanticScholarClient(cache, rate_limit_delay=0.5)
```

### Batch Operations
Reduce tool calls:

```python
# Bad: Multiple searches
for query in queries:
    arxiv.search(query)

# Good: Single deduplication at end
all_papers = []
for query in queries:
    all_papers.extend(arxiv.search(query)["papers"])
dedupe_result = deduplicator.deduplicate(all_papers)
```

## Monitoring & Observability

### LangSmith Integration

```python
from langsmith import traceable

@traceable
async def search_papers_node(state):
    # Node logic here
    pass
```

### Custom Metrics

```python
def log_tool_metrics(tool_name, latency_ms, cached, error):
    metrics = {
        "tool": tool_name,
        "latency_ms": latency_ms,
        "cached": cached,
        "error": error,
    }
    # Send to monitoring system
    logger.info(f"Tool metrics: {metrics}")
```

## Troubleshooting

### MCP Server Won't Start
```bash
# Check Python version
python3 --version  # Should be 3.11+

# Verify dependencies
pip list | grep -E "(mcp|requests)"

# Test import
python3 -c "from mcp.server import Server; print('OK')"
```

### Tool Not Found
```bash
# Verify server is running
ps aux | grep "python -m mcp"

# Check stderr for startup errors
# (logs go to stderr, not stdout)
```

### Slow Responses
```bash
# Check cache stats
python3 -c "from mcp.cache import RequestCache; print(RequestCache().stats())"

# Run warmup if needed
python3 scripts/warmup_cache.py
```

### ArXiv Rate Limit
- Wait a few minutes before retrying
- Pre-populate cache before evaluation runs
- Consider smaller `max_results` per query

## API Compliance

### ArXiv Terms of Service
- Max 1 request every 3 seconds
- Respectful User-Agent headers
- Cache responses aggressively
- See: https://info.arxiv.org/help/api/index.html

### Semantic Scholar Terms
- No explicit rate limits for free tier
- Reasonable use policy
- See: https://api.semanticscholar.org/

## Next Steps

1. **Test the connection**: Run integration tests with agent
2. **Profile performance**: Measure latency and cache hit rates
3. **Set up monitoring**: Instrument with LangSmith or MLFlow
4. **Run evaluation**: Evaluate agent on 30-task eval set
5. **Optimize**: Tweak rate limits and cache strategy based on metrics

See `/Users/mac/nlp_lab5/eval/` for evaluation set and metrics collection.
