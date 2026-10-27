import json
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from creatorpal_agent.backends import CorpusBackend


@pytest.mark.asyncio
async def test_real_stdio_tools_and_validation():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "creatorpal_agent.mcp_server"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert names == {"search_communities", "read_community_rules"}
            backend = CorpusBackend()
            profile = next(d for d in backend.documents if d.kind == "profile")
            query = profile.text.split()[0]
            found = await client.call_tool("search_communities", {"query": query, "limit": 2})
            assert not found.isError
            assert json.loads(found.content[0].text)["evidence"] == backend.search(query, 2)
            rules = await client.call_tool("read_community_rules", {"community": profile.community})
            assert not rules.isError
            assert json.loads(rules.content[0].text)["evidence"] == backend.rules(profile.community)
            bad = await client.call_tool("search_communities", {"query": query, "limit": -1})
            assert bad.isError
            blank = await client.call_tool("search_communities", {"query": " "})
            assert blank.isError
            missing = await client.call_tool("read_community_rules", {"community": "__unknown__"})
            assert json.loads(missing.content[0].text)["evidence"] == []
