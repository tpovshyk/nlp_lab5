"""Tests for literature tools."""

import pytest
from pathlib import Path
import tempfile
import sys

# Add mcp_literature_server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_literature_server"))

from cache import RequestCache
from literature_tools import (
    ArxivSearcher,
    SemanticScholarClient,
    PaperDeduplicator,
    LiteratureToolsError,
)


@pytest.fixture
def cache():
    """Create a temporary cache for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield RequestCache(tmpdir)


class TestRequestCache:
    """Test cache functionality."""
    
    def test_cache_set_and_get(self, cache):
        """Test basic cache set/get."""
        request = {"query": "test", "year": 2020}
        response = {"papers": [{"title": "Test Paper"}]}
        
        # Should miss initially
        assert cache.get("test_api", request) is None
        
        # Set and retrieve
        cache.set("test_api", request, response)
        cached = cache.get("test_api", request)
        assert cached == response
    
    def test_cache_keying_by_request(self, cache):
        """Test that cache keys are based on request, not task."""
        request1 = {"query": "transformers", "year": 2020}
        request2 = {"query": "transformers", "year": 2020}  # Same request
        
        response = {"papers": [{"id": "1"}]}
        cache.set("arxiv", request1, response)
        
        # Different request objects, same content -> should hit cache
        assert cache.get("arxiv", request2) == response
    
    def test_cache_stats(self, cache):
        """Test cache statistics."""
        cache.set("arxiv", {"q": "test"}, {"p": 1})
        cache.set("arxiv", {"q": "test2"}, {"p": 2})
        cache.set("s2", {"id": "123"}, {"p": 3})
        
        stats = cache.stats()
        assert stats["total_entries"] == 3
        assert stats["by_source"]["arxiv"] == 2
        assert stats["by_source"]["s2"] == 1


class TestArxivSearcher:
    """Test arXiv search tool."""
    
    def test_arxiv_searcher_init(self, cache):
        """Test searcher initialization."""
        searcher = ArxivSearcher(cache)
        assert searcher.cache is cache
    
    def test_cache_hit(self, cache):
        """Test that cached results are returned with cached=True flag."""
        searcher = ArxivSearcher(cache)
        
        # Pre-populate cache
        request = {"query": "test", "year_from": None, "max_results": 10}
        cached_response = {"papers": [{"title": "Cached"}]}
        cache.set("arxiv", request, cached_response)
        
        # Search should return with cached flag
        result = searcher.search("test")
        assert result["cached"] is True
        assert result["papers"][0]["title"] == "Cached"


class TestPaperDeduplicator:
    """Test deduplication logic."""
    
    def test_deduplicate_empty_list(self, cache):
        """Test deduplication of empty list."""
        dedup = PaperDeduplicator(cache)
        result = dedup.deduplicate([])
        
        assert result["papers"] == []
        assert result["duplicate_groups"] == []
    
    def test_deduplicate_by_doi(self, cache):
        """Test deduplication by DOI."""
        dedup = PaperDeduplicator(cache)
        
        papers = [
            {
                "paper_id": "1",
                "title": "Same Paper A",
                "doi": "10.1234/test",
            },
            {
                "paper_id": "2",
                "title": "Same Paper B",
                "doi": "10.1234/test",  # Same DOI
            },
        ]
        
        result = dedup.deduplicate(papers)
        assert len(result["papers"]) == 1
        assert len(result["duplicate_groups"]) == 1
        assert set(result["duplicate_groups"][0]) == {"1", "2"}
    
    def test_deduplicate_by_arxiv_id(self, cache):
        """Test deduplication by arXiv ID."""
        dedup = PaperDeduplicator(cache)
        
        papers = [
            {
                "paper_id": "1",
                "title": "Paper A",
                "arxiv_id": "2020.12345",
            },
            {
                "paper_id": "2",
                "title": "Paper B",
                "arxiv_id": "2020.12345",  # Same arXiv ID
            },
        ]
        
        result = dedup.deduplicate(papers)
        assert len(result["papers"]) == 1
        assert len(result["duplicate_groups"]) == 1
    
    def test_deduplicate_by_title(self, cache):
        """Test deduplication by normalized title."""
        dedup = PaperDeduplicator(cache)
        
        papers = [
            {
                "paper_id": "1",
                "title": "Attention Is All You Need",
            },
            {
                "paper_id": "2",
                "title": "Attention is all you need!",  # Different punctuation/case
            },
        ]
        
        result = dedup.deduplicate(papers)
        assert len(result["papers"]) == 1
        assert len(result["duplicate_groups"]) == 1
    
    def test_no_duplicates(self, cache):
        """Test list with no duplicates."""
        dedup = PaperDeduplicator(cache)
        
        papers = [
            {"paper_id": "1", "title": "Paper One", "doi": "10.1111/a"},
            {"paper_id": "2", "title": "Paper Two", "doi": "10.1111/b"},
        ]
        
        result = dedup.deduplicate(papers)
        assert len(result["papers"]) == 2
        assert result["duplicate_groups"] == []


class TestLiteratureToolsError:
    """Test error handling."""
    
    def test_retriable_error(self):
        """Test retriable error flag."""
        err = LiteratureToolsError("Network timeout", is_retriable=True)
        assert err.is_retriable is True
    
    def test_non_retriable_error(self):
        """Test non-retriable error flag."""
        err = LiteratureToolsError("Invalid query", is_retriable=False)
        assert err.is_retriable is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
