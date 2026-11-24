"""Run explicitly with 'uv run pytest tests/npx_smoke.py' on a host with npm, npx and uv."""

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_packed_mcp_starts_from_an_unrelated_directory(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = {"npm_config_cache": str(tmp_path / "npm cache")}
    packed = subprocess.run(
        [shutil.which("npm"), "pack", "--json", "--pack-destination", str(tmp_path)],
        cwd=root, env={**os.environ, **env}, check=True, capture_output=True, text=True,
    )
    package = json.loads(packed.stdout)[0]
    archive = tmp_path / package["filename"]
    cwd = tmp_path / "mcp client"
    cwd.mkdir()
    # Reuse the documented client configuration, substituting this build's archive.
    config = json.loads((root / "examples/mcp.npx.json").read_text())["mcpServers"]["grandma2-toolkit"]
    assert config["args"] == ["--yes", package["name"]]
    params = StdioServerParameters(
        command=config["command"], args=["--yes", f"file:{archive}"], cwd=str(cwd),
        env={**env, **{k: v for k, v in os.environ.items() if k in ("UV_CACHE_DIR", "UV_OFFLINE")},
             "MA2_OUTPUT_DIR": str(tmp_path / "audit"), "MA2_PASSWORD": ""},
    )

    async def discover():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"ma2_connections", "ma2_execute", "ma3d_capture"} <= names
            # validate() fails before opening a socket, leaving the configured audit trace.
            status = await session.call_tool("ma2_status", {})
            assert status.isError and "MA2_PASSWORD" in status.content[0].text
            assert list((tmp_path / "audit").glob("*/audit.json"))

    asyncio.run(discover())
