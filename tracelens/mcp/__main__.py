"""Entry point for running TraceLens as an MCP server."""

from tracelens.mcp import mcp

if __name__ == "__main__":
    mcp.run()
