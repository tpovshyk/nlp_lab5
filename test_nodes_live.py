#!/usr/bin/env python3
"""Test the updated nodes with real agent flow."""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_nodes():
    """Test classify_task and search_papers nodes."""
    from research_agent.graph import build_graph
    from research_agent.state import AgentState
    
    print("🧪 Testing Updated Nodes\n")
    
    # Build graph
    print("1. Building graph...")
    graph = build_graph()
    print("✅ Graph compiled\n")
    
    # Create test state
    test_question = "Find top 3 cited papers on transformers after 2020"
    initial_state = {
        "user_question": test_question,
        "papers": [],
        "plan": [],
        "evidence": [],
        "tool_calls": [],
        "transient_notes": [],
        "task_type": None,
    }
    
    print(f"2. Running agent with query: '{test_question}'\n")
    
    try:
        # Run the graph
        result = graph.invoke(initial_state)
        
        print("✅ Agent execution completed!\n")
        print("=" * 60)
        print("RESULTS:")
        print("=" * 60)
        print(f"Task Type: {result.get('task_type')}")
        print(f"Papers Found: {len(result.get('papers', []))}")
        print(f"Tool Calls: {len(result.get('tool_calls', []))}")
        print(f"Final Answer: {result.get('final_answer', 'N/A')[:100]}...")
        print("\nTransient Notes:")
        for note in result.get("transient_notes", []):
            print(f"  • {note}")
        
        if result.get("papers"):
            print(f"\nFirst Paper: {result['papers'][0]}")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_nodes())
    sys.exit(0 if result else 1)
