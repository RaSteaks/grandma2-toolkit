"""Official MCP SDK stdio server. Stdout is reserved for MCP JSON-RPC."""

import base64
import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, ImageContent, TextContent, ToolAnnotations

from .service import Toolkit

mcp = FastMCP("grandma2-toolkit")
# Typed dictionary returns produce MCP structuredContent as well as readable text.
toolkit = Toolkit()
READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False)
FILE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


@mcp.tool(annotations=READ)
def ma2_connections() -> dict[str, Any]:
    """Connect onPC and MA3D simultaneously; return runtime identity, Show and session state for each."""
    return toolkit.connections()


@mcp.tool(annotations=READ)
def ma2_status(target: str = "onpc") -> dict[str, Any]:
    """Inspect one verified runtime: target is onpc or ma3d. Does not change the Show."""
    return toolkit.status(target)


@mcp.tool(annotations=READ)
def ma2_list(object: str, target: str = "onpc") -> dict[str, Any]:
    """Read a native object, range, or children. Examples: Root 10.4.*, Sequence 121 Cue 1 Thru 5,
    MAtricks 1 Thru 10, LiveSetup.FixtureTypes, Screen 2.*, ViewButton 2.1 Thru 2.10 /screen=2.
    Pass the object expression without the List keyword. Returns the console's native text.
    """
    return toolkit.list_objects(object, target)


@mcp.tool(annotations=WRITE)
def ma2_execute(commands: list[str], expected_show: str, target: str = "onpc") -> dict[str, Any]:
    """Execute up to 100 authorized commands sequentially; requires MA2_ALLOW_WRITE=1 and matching Show.

    Not transactional. Stops at first failure; prior commands may already be applied.
    Do not retry after a timeout without querying state. User scope still governs every command.
    """
    return toolkit.execute(commands, expected_show, target)


@mcp.tool(annotations=FILE)
def ma2_export(object: str, target: str = "onpc") -> dict[str, Any]:
    """Export a local object or pool range (including Effect, MAtricks and Macro) to XML and fingerprint it."""
    return toolkit.export_object(object, target)


@mcp.tool(annotations=FILE)
def ma2_backup(expected_show: str) -> dict[str, Any]:
    """Save onPC Show, wait for asynchronous completion, copy a new backup and return SHA256. Write gate applies."""
    return toolkit.backup_show(expected_show)


@mcp.tool(annotations=WRITE)
def ma3d_transform(object: str, expected_show: str, values: dict[str, float], target: str = "ma3d") -> dict[str, Any]:
    """Set x/y/z (metres), rx/ry/rz (degrees), or camera fov (radians), and return before/after List.

    Requires an inspected scene Root address or Camera number. Installation orientation is NOT
    programmed Pan/Tilt. MA3D edits can synchronize into onPC. Use target=onpc if its shared scene
    is the intended authority. Requires write gate and expected Show; no visual pass is implied.
    """
    return toolkit.set_transform(object, expected_show, values, target)


@mcp.tool(annotations=FILE)
def ma3d_capture(window_title: str | None = None) -> CallToolResult:
    """Save the uniquely identified visible local MA3D window as PNG, without UI input.

    Windows only. Read the returned image to inspect the camera and beams. Does not start
    playback, select Front, or certify visual acceptance. Minimized/blank/ambiguous windows fail.
    """
    result = toolkit.capture_ma3d(window_title)
    # Return both a persistent evidence path and native MCP image content for visual hosts.
    data = Path(result["file"]).read_bytes()
    content = [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    if len(data) <= 10 * 1024 * 1024:
        content.append(ImageContent(type="image", mimeType="image/png", data=base64.b64encode(data).decode("ascii")))
    return CallToolResult(content=content, structuredContent=result)


def main():
    """Start only the stdio transport; there is no unauthenticated HTTP control port."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
