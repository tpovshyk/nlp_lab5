"""Entry point for running the MCP server as a module.

Usage:
  python -m mcp_literature_server
  python -m mcp_literature_server --cache-dir /tmp/cache
"""

import argparse
import sys
from pathlib import Path

# Add server module to path
sys.path.insert(0, str(Path(__file__).parent))

from research_server import ResearchAgentServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Research Agent MCP Server")
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="Directory for cache storage (default: .cache)",
    )
    args = parser.parse_args()
    
    server = ResearchAgentServer(cache_dir=args.cache_dir)
    server.run()


if __name__ == "__main__":
    main()
