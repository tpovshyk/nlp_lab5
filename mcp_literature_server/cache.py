"""Request-based caching for external API responses.

Cache keys are derived from API request parameters, NOT from evaluation task IDs.
This ensures that identical requests (even from different tasks) reuse cached results.
"""

import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Optional


class RequestCache:
    """SQLite-backed cache for API responses, keyed by request hash."""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache with optional custom directory."""
        if cache_dir is None:
            cache_dir = Path(__file__).parent / ".cache"
        else:
            cache_dir = Path(cache_dir)
        
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = cache_dir / "api_cache.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema if needed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    request_hash TEXT PRIMARY KEY,
                    request_key TEXT NOT NULL,
                    api_source TEXT NOT NULL,
                    response TEXT NOT NULL,
                    stored_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _hash_request(self, request_dict: dict) -> str:
        """Generate a deterministic hash of the request parameters."""
        # Sort keys for deterministic ordering
        request_json = json.dumps(request_dict, sort_keys=True)
        return hashlib.sha256(request_json.encode()).hexdigest()

    def get(self, api_source: str, request_params: dict) -> Optional[Any]:
        """Retrieve cached response for a request."""
        request_hash = self._hash_request(request_params)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT response FROM cache 
                WHERE api_source = ? AND request_hash = ?
                """,
                (api_source, request_hash),
            )
            row = cursor.fetchone()
        
        if row:
            return json.loads(row[0])
        return None

    def set(
        self,
        api_source: str,
        request_params: dict,
        response: Any,
    ) -> None:
        """Store API response in cache."""
        request_hash = self._hash_request(request_params)
        request_key = json.dumps(request_params, sort_keys=True)
        response_json = json.dumps(response, default=str)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache 
                (api_source, request_hash, request_key, response) 
                VALUES (?, ?, ?, ?)
                """,
                (api_source, request_hash, request_key, response_json),
            )
            conn.commit()

    def clear(self) -> None:
        """Clear all cached entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()

    def stats(self) -> dict:
        """Return cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT api_source, COUNT(*) as cnt FROM cache GROUP BY api_source"
            )
            by_source = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {"total_entries": count, "by_source": by_source}
