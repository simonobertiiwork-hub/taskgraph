"""End-to-end smoke test for TaskGraph's MCP stdio server."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.ai.mcp_server import SERVER_NAME
from app.ai.schemas import RunScenario


@dataclass(frozen=True, slots=True)
class MCPSmokeConfig:
    results_dir: Path = Path("demos/results")
    scenario: RunScenario = RunScenario.CONNECTION_POOL_EXHAUSTION


async def run_mcp_smoke(config: MCPSmokeConfig) -> dict[str, object]:
    env = os.environ.copy()
    env["TASKGRAPH_RESULTS_DIR"] = str(config.results_dir.resolve())
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.ai.mcp_server"],
        env=env,
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            initialize = await session.initialize()
            listed = await session.list_tools()
            result = await session.call_tool(
                "get_incident_evidence",
                {"scenario": config.scenario.value},
                read_timeout_seconds=timedelta(seconds=30),
            )
    tool_names = sorted(tool.name for tool in listed.tools)
    payload = result.structuredContent
    passed = (
        not result.isError
        and payload is not None
        and payload.get("scenario") == config.scenario.value
        and bool(payload.get("evidence"))
        and {"get_incident_evidence", "list_incident_scenarios"}.issubset(tool_names)
    )
    return {
        "passed": passed,
        "server_name": initialize.serverInfo.name or SERVER_NAME,
        "tools": tool_names,
        "scenario": config.scenario.value,
    }
