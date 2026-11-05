"""MCP server: lets Claude (claude.ai, Claude Desktop, Claude Code) use the site tools."""
from __future__ import annotations

from typing import Any

import mcp_types as t
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings

from .connectors import Registry, build_tools

INSTRUCTIONS = (
    "Tools for Marlen's websites (iMARLEN). Tool names are `<site>__<action>`. "
    "`<site>__fetch_page` reads any public page of that site. Tools that change data "
    "(POST/PUT/PATCH/DELETE) are marked destructive: describe the change and get the user's "
    "go-ahead before calling them."
)


def create_mcp_server(registry: Registry) -> Server:
    tools = build_tools(registry.sites, audience="mcp")

    async def list_tools(ctx: Any, params: Any) -> t.ListToolsResult:
        out = []
        for tool in tools.values():
            d = tool.definition()
            out.append(t.Tool(
                name=d["name"], description=d["description"], input_schema=d["input_schema"],
                annotations=t.ToolAnnotations(
                    title=f"{tool.site.name}: {tool.spec.name}",
                    read_only_hint=not tool.spec.writes,
                    destructive_hint=tool.spec.writes,
                    open_world_hint=False,
                ),
            ))
        return t.ListToolsResult(tools=out)

    async def call_tool(ctx: Any, params: t.CallToolRequestParams) -> t.CallToolResult:
        tool = tools.get(params.name)
        if tool is None:
            return t.CallToolResult(content=[t.TextContent(type="text", text=f"Белгісіз құрал: {params.name}")],
                                    is_error=True)
        text, is_error = await registry.run(tool, params.arguments or {})
        return t.CallToolResult(content=[t.TextContent(type="text", text=text)], is_error=is_error)

    return Server("imarlen-sites", version="0.1.0", instructions=INSTRUCTIONS,
                  on_list_tools=list_tools, on_call_tool=call_tool)


def mcp_starlette(server: Server, public_host: str):
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[public_host, "127.0.0.1:*", "localhost:*", "testserver"],
        allowed_origins=[f"https://{public_host}", "https://claude.ai", "http://localhost:*"],
    )
    return server.streamable_http_app(streamable_http_path="/mcp", stateless_http=True,
                                      json_response=True, transport_security=security)
