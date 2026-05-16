"""
GCP Demo Block 4 — Python MCP client driving the Go risk-score tool.

Spawns ./risk-tool (the Go binary built in this directory) as a subprocess,
opens an MCP session over stdio, lists tools, and calls risk_score on three
sample orders that hit the three decision bands (approve / review / decline).

Run:
    go build -o risk-tool .             # one-time
    pip install mcp --break-system-packages
    python demo_client.py
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BINARY = str(Path(__file__).parent / "risk-tool")

SAMPLES = [
    {
        "label": "Low-risk: returning retail buyer, has JCIC",
        "args": {
            "merchant_segment": "retail",
            "is_new_buyer": False,
            "order_value_twd": 2500,
            "has_jcic": True,
        },
    },
    {
        "label": "Medium-risk: new travel buyer, has JCIC, within cap",
        "args": {
            "merchant_segment": "travel",
            "is_new_buyer": True,
            "order_value_twd": 25000,
            "has_jcic": True,
        },
    },
    {
        "label": "High-risk: new travel buyer, NO JCIC, over cap",
        "args": {
            "merchant_segment": "travel",
            "is_new_buyer": True,
            "order_value_twd": 45000,
            "has_jcic": False,
        },
    },
]


async def main() -> None:
    params = StdioServerParameters(command=BINARY)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"Connected to MCP server: {init.serverInfo.name} "
                  f"v{init.serverInfo.version}")

            tools = await session.list_tools()
            print(f"Tools exposed: {[t.name for t in tools.tools]}")

            for sample in SAMPLES:
                print("\n" + "-" * 72)
                print(f"CASE: {sample['label']}")
                print(f"  args: {sample['args']}")
                result = await session.call_tool("risk_score", sample["args"])
                payload = result.content[0].text
                parsed = json.loads(payload)
                print(f"  score={parsed['score']:.2f}  band={parsed['band']}  "
                      f"decision={parsed['decision']}")
                print("  contributions:")
                for c in parsed["contributions"]:
                    print(f"    - {c}")

    print("\n" + "=" * 72)
    print("BLOCK 4 COMPLETE ✅")
    print("  Go MCP server: risk-tool (mark3labs/mcp-go v0.54.0)")
    print("  Python client: mcp SDK (stdio transport)")
    print("  Tool:          risk_score  (rule-based, derived from Block 2 policy docs)")
    print("Next: Block 5 (Cloud Run + LangSmith observability)")


if __name__ == "__main__":
    asyncio.run(main())
