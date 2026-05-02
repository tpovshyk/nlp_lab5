#!/usr/bin/env python3
"""Quick verification script for MCP server setup."""

import sys
from pathlib import Path

# Add mcp_literature_server to path
mcp_dir = Path(__file__).parent / "mcp_literature_server"
sys.path.insert(0, str(mcp_dir))

def verify_imports():
    """Check all imports work."""
    print("✓ Verifying imports...")
    try:
        from cache import RequestCache
        from literature_tools import (
            ArxivSearcher,
            SemanticScholarClient,
            PaperDeduplicator,
            LiteratureToolsError,
        )
        from research_server import ResearchAgentServer
        print("  ✓ All imports successful")
        return True
    except ImportError as e:
        print(f"  ✗ Import error: {e}")
        return False

def verify_cache():
    """Test cache functionality."""
    print("✓ Verifying cache...")
    import tempfile
    from cache import RequestCache
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = RequestCache(tmpdir)
            
            # Test set/get
            request = {"query": "test"}
            response = {"papers": []}
            cache.set("test", request, response)
            
            cached = cache.get("test", request)
            assert cached == response, "Cache get/set failed"
            
            # Test stats
            stats = cache.stats()
            assert stats["total_entries"] == 1, "Stats incorrect"
            
            print("  ✓ Cache working correctly")
            return True
    except Exception as e:
        print(f"  ✗ Cache error: {e}")
        return False

def verify_deduplication():
    """Test deduplication logic."""
    print("✓ Verifying deduplication...")
    import tempfile
    from cache import RequestCache
    from literature_tools import PaperDeduplicator
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = RequestCache(tmpdir)
            dedup = PaperDeduplicator(cache)
            
            # Test with duplicates
            papers = [
                {"paper_id": "1", "title": "Test Paper", "doi": "10.1234/test"},
                {"paper_id": "2", "title": "Test Paper", "doi": "10.1234/test"},  # Duplicate
            ]
            
            result = dedup.deduplicate(papers)
            assert len(result["papers"]) == 1, "Deduplication failed"
            assert len(result["duplicate_groups"]) == 1, "Duplicate detection failed"
            
            print("  ✓ Deduplication working correctly")
            return True
    except Exception as e:
        print(f"  ✗ Deduplication error: {e}")
        return False

def verify_server():
    """Test MCP server setup."""
    print("✓ Verifying MCP server...")
    import tempfile
    from research_server import ResearchAgentServer
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            server = ResearchAgentServer(cache_dir=tmpdir)
            tools = server.get_tools()
            
            # Check tools
            tool_names = [t["name"] for t in tools]
            assert "search_arxiv" in tool_names, "search_arxiv tool not found"
            assert "get_semantic_scholar_paper" in tool_names, "get_semantic_scholar_paper tool not found"
            assert "deduplicate_papers" in tool_names, "deduplicate_papers tool not found"
            
            # Check schemas
            for tool in tools:
                assert "inputSchema" in tool, f"Tool {tool['name']} missing schema"
                assert "description" in tool, f"Tool {tool['name']} missing description"
            
            print("  ✓ MCP server configured correctly")
            print(f"    - Found {len(tools)} tools")
            for tool in tools:
                print(f"      • {tool['name']}")
            return True
    except Exception as e:
        print(f"  ✗ Server error: {e}")
        return False

def main():
    """Run all verifications."""
    print("\n" + "="*60)
    print("MCP Server Verification")
    print("="*60 + "\n")
    
    checks = [
        verify_imports,
        verify_cache,
        verify_deduplication,
        verify_server,
    ]
    
    results = [check() for check in checks]
    
    print("\n" + "="*60)
    if all(results):
        print("✅ All checks passed!")
        print("="*60)
        print("\nNext steps:")
        print("  1. Start MCP server: python -m mcp")
        print("  2. Test with live queries")
        print("  3. Connect to agent in search_papers node")
        print("="*60 + "\n")
        return 0
    else:
        print("❌ Some checks failed")
        print("="*60 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
