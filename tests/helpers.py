"""Helpers shared by the tool tests."""

from fastmcp import FastMCP


async def call(mcp: FastMCP, name: str, arguments: dict):
    tool = await mcp.get_tool(name)
    assert tool is not None, f"tool {name!r} is not registered"
    return await tool.run(arguments)
