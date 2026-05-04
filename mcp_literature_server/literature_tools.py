"""Literature data tools: arXiv search, Semantic Scholar lookups, deduplication."""

import logging
import sys
from typing import Optional, Callable
import time

import requests

from .cache import RequestCache


logger = logging.getLogger(__name__)


class LiteratureToolsError(Exception):
    """Base exception for literature tools."""
    
    is_retriable: bool = False
    
    def __init__(self, message: str, is_retriable: bool = False):
        super().__init__(message)
        self.is_retriable = is_retriable


_RETRY_BACKOFF_SECONDS = (5.0, 15.0, 30.0)


class ArxivSearcher:
    """Fetch papers from arXiv API with caching and retry logic."""

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self, cache: RequestCache, rate_limit_delay: float = 3.0):
        self.cache = cache
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _enforce_rate_limit(self) -> None:
        """Respect arXiv rate limit: max ~1 request per 3 seconds."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

    def search(
        self,
        query: str,
        year_from: Optional[int] = None,
        max_results: int = 10,
    ) -> dict:
        """
        Search arXiv for papers.
        
        Args:
            query: Search string (e.g., "retrieval augmented generation")
            year_from: Minimum publication year (optional)
            max_results: Maximum number of results (default 10, arXiv limit 30000)
        
        Returns:
            dict with 'papers' list and 'cached' boolean
        
        Raises:
            LiteratureToolsError: On network or parsing errors
        """
        # Build request params for caching key
        request_params = {
            "query": query,
            "year_from": year_from,
            "max_results": min(max_results, 100),  # arXiv max per page
        }
        
        # Check cache first
        cached_response = self.cache.get("arxiv", request_params)
        if cached_response:
            logger.info(f"Cache hit for arXiv query: {query}")
            return {**cached_response, "cached": True}
        
        # Build arXiv query string
        arxiv_query = query
        if year_from:
            # arXiv submittedDate format: YYYYMMDDHHMMSS
            from datetime import date
            today = date.today().strftime("%Y%m%d") + "000000"
            arxiv_query += f" AND submittedDate:[{year_from}0101000000 TO {today}]"
        
        params = {
            "search_query": arxiv_query,
            "start": 0,
            "max_results": min(max_results, 100),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        
        last_error: Exception | None = None
        for attempt in range(len(_RETRY_BACKOFF_SECONDS) + 1):
            try:
                self._enforce_rate_limit()
                response = requests.get(self.BASE_URL, params=params, timeout=10)
                self._last_request_time = time.time()

                if response.status_code == 429:
                    last_error = LiteratureToolsError(
                        "arXiv API rate limit exceeded",
                        is_retriable=True,
                    )
                else:
                    response.raise_for_status()
                    papers = self._parse_arxiv_response(response.text, year_from)
                    result = {"papers": papers}
                    self.cache.set("arxiv", request_params, result)
                    logger.info(
                        f"Retrieved {len(papers)} papers from arXiv for query: {query}"
                    )
                    return {**result, "cached": False}

            except requests.RequestException as e:
                last_error = LiteratureToolsError(
                    f"arXiv API request failed: {e}",
                    is_retriable=True,
                )
            except LiteratureToolsError as e:
                if not e.is_retriable:
                    raise
                last_error = e
            except Exception as e:
                raise LiteratureToolsError(
                    f"Failed to parse arXiv response: {e}",
                    is_retriable=False,
                ) from e

            if attempt < len(_RETRY_BACKOFF_SECONDS):
                delay = _RETRY_BACKOFF_SECONDS[attempt]
                logger.warning(
                    f"arXiv attempt {attempt + 1} failed ({last_error}); retrying in {delay}s"
                )
                time.sleep(delay)

        assert last_error is not None
        raise last_error

    def _parse_arxiv_response(self, xml_text: str, year_from: Optional[int]) -> list:
        """Parse arXiv Atom feed response."""
        import xml.etree.ElementTree as ET
        
        papers = []
        try:
            root = ET.fromstring(xml_text)
            
            # Define namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                # Extract fields
                title = entry.findtext('atom:title', namespaces=ns) or ""
                title = title.replace('\n', ' ').strip()

                arxiv_id = entry.findtext('atom:id', namespaces=ns) or ""
                arxiv_id = arxiv_id.replace('http://arxiv.org/abs/', '').replace('https://arxiv.org/abs/', '')

                authors_list = []
                for author in entry.findall('atom:author', ns):
                    name = author.findtext('atom:name', namespaces=ns)
                    if name:
                        authors_list.append(name)

                published = entry.findtext('atom:published', namespaces=ns) or ""
                year = int(published[:4]) if published else None

                # Filter by year if specified
                if year_from and year and year < year_from:
                    continue

                abstract = entry.findtext('atom:summary', namespaces=ns) or ""
                abstract = abstract.replace('\n', ' ').strip()
                
                # Extract DOI if present
                doi = None
                for link in entry.findall('atom:link', ns):
                    if link.get('title') == 'doi':
                        doi = link.get('href', '').replace('http://dx.doi.org/', '')
                
                paper = {
                    "paper_id": arxiv_id,
                    "arxiv_id": arxiv_id,
                    "title": title,
                    "year": year,
                    "authors": authors_list,
                    "abstract": abstract,
                    "doi": doi,
                    "source_tool": "search_arxiv",
                }
                papers.append(paper)
        
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse XML: {e}")
        
        return papers


class SemanticScholarClient:
    """Fetch paper metadata and relationships from Semantic Scholar API."""
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    def __init__(self, cache: RequestCache, rate_limit_delay: float = 1.0):
        self.cache = cache
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0.0

    def _enforce_rate_limit(self) -> None:
        """Respect Semantic Scholar rate limit."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

    def get_paper(
        self,
        paper_id_or_title: str,
        include_references: bool = True,
        include_citations: bool = True,
    ) -> dict:
        """
        Retrieve a paper and optionally its references/citations.
        
        Args:
            paper_id_or_title: Either a paper ID (arXiv, DOI, or S2 ID) or a title
            include_references: Fetch papers this paper references
            include_citations: Fetch papers that cite this paper
        
        Returns:
            dict with paper metadata and optionally references/citations
        
        Raises:
            LiteratureToolsError: On API or network errors
        """
        request_params = {
            "paper_id_or_title": paper_id_or_title,
            "include_references": include_references,
            "include_citations": include_citations,
        }
        
        # Check cache
        cached = self.cache.get("semantic_scholar", request_params)
        if cached:
            logger.info(f"Cache hit for Semantic Scholar: {paper_id_or_title}")
            return {**cached, "cached": True}
        
        try:
            self._enforce_rate_limit()
            
            # Try to resolve paper ID
            paper_info = self._resolve_paper_id(paper_id_or_title)
            if not paper_info:
                raise LiteratureToolsError(
                    f"Paper not found: {paper_id_or_title}",
                    is_retriable=False,
                )
            
            paper_id = paper_info["paperId"]
            
            # Fetch full paper details
            fields = [
                "paperId", "title", "authors", "year", "abstract",
                "venue", "externalIds", "citationCount", "referenceCount",
            ]
            
            if include_references or include_citations:
                fields.extend(["references", "citations"])
            
            paper_response = self._fetch_paper(paper_id, fields)
            
            result = {"paper": paper_response}
            
            # Parse references and citations if requested
            if include_references:
                refs = paper_response.get("references", [])
                result["references"] = self._extract_paper_list(refs)
            else:
                result["references"] = []
            
            if include_citations:
                cites = paper_response.get("citations", [])
                result["citations"] = self._extract_paper_list(cites)
            else:
                result["citations"] = []
            
            # Cache the result
            self.cache.set("semantic_scholar", request_params, result)
            logger.info(f"Retrieved paper from Semantic Scholar: {paper_id}")
            return {**result, "cached": False}
            
        except LiteratureToolsError:
            raise
        except requests.RequestException as e:
            raise LiteratureToolsError(
                f"Semantic Scholar API request failed: {e}",
                is_retriable=True,
            ) from e
        except Exception as e:
            raise LiteratureToolsError(
                f"Unexpected error querying Semantic Scholar: {e}",
                is_retriable=False,
            ) from e

    def _resolve_paper_id(self, identifier: str) -> Optional[dict]:
        """Resolve a paper ID or title to a Semantic Scholar paper ID."""
        # Try direct lookup first (for arXiv, DOI, S2 ID)
        paper = self._fetch_paper(identifier, ["paperId", "title"])
        if paper:
            return paper
        
        # Fall back to search by title
        try:
            self._enforce_rate_limit()
            url = f"{self.BASE_URL}/paper/search"
            params = {"query": identifier, "limit": 1}
            response = requests.get(url, params=params, timeout=10)
            self._last_request_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    return data["data"][0]
        except Exception as e:
            logger.warning(f"Failed to search by title: {e}")
        
        return None

    def _fetch_paper(self, paper_id: str, fields: list) -> Optional[dict]:
        """Fetch a paper by ID with specified fields, with retry on transient errors."""
        url = f"{self.BASE_URL}/paper/{paper_id}"
        params = {"fields": ",".join(fields)}

        last_error: Exception | None = None
        for attempt in range(len(_RETRY_BACKOFF_SECONDS) + 1):
            try:
                self._enforce_rate_limit()
                response = requests.get(url, params=params, timeout=10)
                self._last_request_time = time.time()

                if response.status_code == 200:
                    return response.json()
                if response.status_code == 404:
                    return None
                if response.status_code == 429:
                    last_error = LiteratureToolsError(
                        "Semantic Scholar rate limit exceeded",
                        is_retriable=True,
                    )
                else:
                    response.raise_for_status()
            except requests.RequestException as e:
                logger.warning(f"Failed to fetch paper {paper_id}: {e}")
                last_error = LiteratureToolsError(str(e), is_retriable=True)
            except LiteratureToolsError as e:
                if not e.is_retriable:
                    raise
                last_error = e

            if attempt < len(_RETRY_BACKOFF_SECONDS):
                delay = _RETRY_BACKOFF_SECONDS[attempt]
                logger.warning(
                    f"Semantic Scholar attempt {attempt + 1} failed ({last_error}); "
                    f"retrying in {delay}s"
                )
                time.sleep(delay)

        if last_error is not None:
            raise last_error
        return None

    def get_papers_batch(self, ids: list[str], fields: list[str]) -> dict:
        """Fetch many papers in a single POST /paper/batch call.

        Best-effort: returns {"papers": [...]} where missing papers are None.
        On 429 we wait once briefly and retry; otherwise we give up fast so the
        caller can degrade gracefully without burning the wall-clock budget.
        """
        if not ids:
            return {"papers": [], "cached": False}

        request_params = {"ids": sorted(set(ids)), "fields": sorted(set(fields))}
        cached = self.cache.get("semantic_scholar_batch", request_params)
        if cached:
            logger.info(f"Cache hit for S2 batch ({len(ids)} ids)")
            return {**cached, "cached": True}

        url = f"{self.BASE_URL}/paper/batch"
        params = {"fields": ",".join(fields)}
        body = {"ids": list(ids)}

        for attempt in range(2):  # one retry on transient failure
            try:
                self._enforce_rate_limit()
                response = requests.post(url, params=params, json=body, timeout=15)
                self._last_request_time = time.time()

                if response.status_code == 200:
                    data = response.json() or []
                    result = {"papers": data}
                    self.cache.set("semantic_scholar_batch", request_params, result)
                    logger.info(f"S2 batch returned {len(data)} entries for {len(ids)} ids")
                    return {**result, "cached": False}
                if response.status_code == 429:
                    logger.warning(
                        f"S2 batch rate-limited (attempt {attempt + 1}); "
                        f"{'retrying once' if attempt == 0 else 'giving up'}"
                    )
                    if attempt == 0:
                        time.sleep(3.0)
                        continue
                    raise LiteratureToolsError(
                        "Semantic Scholar batch rate limit exceeded",
                        is_retriable=True,
                    )
                response.raise_for_status()
            except requests.RequestException as e:
                if attempt == 0:
                    logger.warning(f"S2 batch request error (attempt 1): {e}; retrying")
                    time.sleep(3.0)
                    continue
                raise LiteratureToolsError(
                    f"Semantic Scholar batch failed: {e}",
                    is_retriable=True,
                ) from e

        return {"papers": [], "cached": False}

    def _extract_paper_list(self, paper_list: list) -> list:
        """Convert S2 paper list to our PaperRecord format."""
        papers = []
        for item in paper_list[:20]:  # Limit to 20 to avoid huge results
            paper_ref = item if isinstance(item, dict) else item.get("paper", {})
            
            paper = {
                "paper_id": paper_ref.get("paperId", ""),
                "title": paper_ref.get("title", ""),
                "year": paper_ref.get("year"),
                "authors": [a.get("name", "") for a in paper_ref.get("authors", [])],
                "abstract": paper_ref.get("abstract"),
                "venue": paper_ref.get("venue"),
                "semantic_scholar_id": paper_ref.get("paperId"),
                "citation_count": paper_ref.get("citationCount"),
                "source_tool": "get_semantic_scholar_paper",
            }
            
            # Extract external IDs
            ext_ids = paper_ref.get("externalIds", {})
            if ext_ids.get("ArXiv"):
                paper["arxiv_id"] = ext_ids["ArXiv"]
            if ext_ids.get("DOI"):
                paper["doi"] = ext_ids["DOI"]
            
            papers.append(paper)
        
        return papers


class PaperDeduplicator:
    """Deduplicate and merge paper records."""
    
    def __init__(self, cache: RequestCache):
        self.cache = cache

    def deduplicate(self, papers: list) -> dict:
        """
        Deduplicate papers by matching on DOI, arXiv ID, or normalized title.
        
        Args:
            papers: List of paper records
        
        Returns:
            dict with 'papers' (deduplicated) and 'duplicate_groups' (list of ID groups)
        """
        if not papers:
            return {"papers": [], "duplicate_groups": []}
        
        # Build indices for matching
        doi_index = {}
        arxiv_index = {}
        title_index = {}
        
        for paper in papers:
            paper_id = paper.get("paper_id") or paper.get("arxiv_id")
            
            if paper.get("doi"):
                doi_index.setdefault(paper["doi"].lower(), []).append(paper_id)
            
            if paper.get("arxiv_id"):
                arxiv_index.setdefault(paper["arxiv_id"], []).append(paper_id)
            
            if paper.get("title"):
                norm_title = self._normalize_title(paper["title"])
                title_index.setdefault(norm_title, []).append(paper_id)
        
        # Find duplicate groups
        seen_ids = set()
        duplicate_groups = []
        unique_papers = {}
        
        for paper in papers:
            paper_id = paper.get("paper_id") or paper.get("arxiv_id")
            
            if paper_id in seen_ids:
                continue
            
            # Find all IDs that match this paper
            group = {paper_id}
            
            if paper.get("doi"):
                group.update(doi_index.get(paper["doi"].lower(), []))
            
            if paper.get("arxiv_id"):
                group.update(arxiv_index.get(paper["arxiv_id"], []))
            
            if paper.get("title"):
                norm_title = self._normalize_title(paper["title"])
                group.update(title_index.get(norm_title, []))
            
            seen_ids.update(group)
            
            if len(group) > 1:
                duplicate_groups.append(list(group))
            
            # Keep first occurrence as canonical
            unique_papers[paper_id] = paper
        
        deduplicated = list(unique_papers.values())
        
        logger.info(
            f"Deduplicated {len(papers)} papers down to {len(deduplicated)} "
            f"({len(duplicate_groups)} duplicate groups)"
        )
        
        return {
            "papers": deduplicated,
            "duplicate_groups": duplicate_groups,
        }

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title for fuzzy matching."""
        import re
        # Remove punctuation, lowercase, collapse whitespace
        normalized = re.sub(r'[^a-z0-9\s]', '', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
