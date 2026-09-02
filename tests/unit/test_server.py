import pytest

from plato_mcp.server import mcp


@pytest.mark.asyncio
async def test_server_boots_with_zero_tools():
    tools = await mcp.list_tools()
    assert tools == []
