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
            assert names == {"ma2_connections", "ma2_status", "ma2_list", "ma2_execute", "ma2_export",
                             "ma2_backup", "ma3d_transform", "ma3d_capture", "ma2_probe", "ma2_read_dmx", "ma2_playback",
                             "ma2_new_show", "ma2_save_show"}
            for tool, args in [("ma2_new_show", {"name": "Rehearsal", "expected_show": "codex"}),
                               ("ma2_save_show", {"expected_show": "codex"})]:
                assert (await session.call_tool(tool, args)).isError
            assert not any(c.startswith(("SaveShow", "NewShow")) for c in onpc.commands)
            both = await session.call_tool("ma2_connections", {})
            assert not both.isError
            assert both.structuredContent["endpoints"]["onpc"]["port"] == onpc.server_address[1]
            probe = await session.call_tool("ma2_probe", {"objects": ["TimecodeSlot 1", "World 1"]})
            assert [r["status"] for r in probe.structuredContent["results"]] == ["acknowledged", "acknowledged"]
            dmx = await session.call_tool("ma2_read_dmx", {"universe": 2, "address": 1, "count": 2})
            assert dmx.structuredContent["values"] == [0, 255]
            assert any("for i=513,514 do" in c for c in onpc.commands)
            blocked = await session.call_tool("ma2_playback", {"executor": "2.1", "action": "go", "expected_show": "codex"})
            assert blocked.isError and "Go Executor 2.1" not in onpc.commands
            result = await session.call_tool("ma2_list", {"object": "Camera 50", "target": "ma3d"})
            assert not result.isError and "灯具" in result.structuredContent["reply"]
            for expression in ("LiveSetup.FixtureTypes", "Root 10.4.*", "FixtureType 1 Thru", "Screen 2.*",
                               "MAtricks 1 Thru 10", "Macro 9", "Sequence 121 Cue 1.5 Thru 5",
                               "ViewButton 2.1 Thru 2.10 /screen=2"):
                result = await session.call_tool("ma2_list", {"object": expression})
                assert not result.isError and f"List {expression}" in onpc.commands
            blocked = await session.call_tool("ma2_execute", {"commands": ["Assign Camera 50 /X=1"], "expected_show": "codex"})
            assert blocked.isError
            assert not any(c.startswith("Assign") for c in onpc.commands)
    asyncio.run(run())
