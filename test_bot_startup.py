#!/usr/bin/env python3
"""Quick test to verify bot can start without errors."""

import sys
import asyncio
from pathlib import Path

# Add to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_bot_startup():
    """Test that bot initializes correctly."""
    from src.research_agent.bot import ResearchAgentBot, check_env
    
    print("🧪 Testing Bot Startup...")
    print()
    
    # Check environment
    print("1. Checking environment...")
    if not check_env():
        print("❌ Environment check failed")
        return False
    print("✅ Environment OK\n")
    
    # Initialize bot
    print("2. Initializing bot...")
    try:
        bot = ResearchAgentBot()
        print("✅ Bot initialized\n")
    except Exception as e:
        print(f"❌ Failed to initialize bot: {e}")
        return False
    
    # Check handlers
    print("3. Checking handlers...")
    handlers = bot.app.handlers
    print(f"✅ Handlers registered: {len(handlers)} handler groups")
    for group_id, handler_list in handlers.items():
        print(f"   - Group {group_id}: {len(handler_list)} handlers")
    print()
    
    print("✅ All startup tests passed!")
    print()
    print("🚀 To run the bot:")
    print("   python -m src.research_agent.bot")
    print()
    print("Then on Telegram:")
    print("   Find: @NLP_05_ResearchAgentBot")
    print("   Send: /start")
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_bot_startup())
    sys.exit(0 if result else 1)
