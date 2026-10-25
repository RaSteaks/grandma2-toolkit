"""Real MCP stdio protocol smoke test against the local TCP console simulator."""

import asyncio
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_mcp_discovery_read_and_write_gate(consoles):
    config, onpc, _ = consoles

    async def run():
        env = {**os.environ, "MA2_HOST": "127.0.0.1", "MA2_PORTS": ",".join(map(str, config.ports)),
               "MA2_PASSWORD": config.password, "MA2_ALLOW_WRITE": "0", "MA2_OUTPUT_DIR": str(config.output_dir)}
        params = StdioServerParameters(command=sys.executable, args=["-m", "grandma2_toolkit.server"], env=env,
                                       cwd=str(Path(__file__).resolve().parents[1]))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            names = {t.name for t in listed.tools}
            assert names == {"ma2_connections", "ma2_status", "ma2_list", "ma2_execute", "ma2_export", "ma2_backup", "ma3d_transform", "ma3d_capture"}
            both = await session.call_tool("ma2_connections", {})
            assert not both.isError
            assert both.structuredContent["endpoints"]["onpc"]["port"] == onpc.server_address[1]
            result = await session.call_tool("ma2_list", {"object": "Camera 50", "target": "ma3d"})
            assert not result.isError and "灯具" in result.structuredContent["reply"]
            blocked = await session.call_tool("ma2_execute", {"commands": ["Assign Camera 50 /X=1"], "expected_show": "codex"})
            assert blocked.isError
            assert not any(c.startswith("Assign") for c in onpc.commands)
    asyncio.run(run())
