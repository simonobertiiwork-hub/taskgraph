"""Read-only MCP server exposing integrity-checked TaskGraph evidence."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from app.ai.repositories.runs import FileRunRepository
from app.ai.schemas import RunScenario
from app.ai.tools.index_scan import IndexScanTools
from app.ai.tools.pool_exhaustion import PoolExhaustionTools
from app.ai.tools.race_condition import RaceConditionTools

SERVER_NAME = "TaskGraph Incident Evidence"
mcp = FastMCP(SERVER_NAME, log_level="ERROR")


def _repository() -> FileRunRepository:
    root = Path(os.getenv("TASKGRAPH_RESULTS_DIR", "demos/results"))
    return FileRunRepository(root)


def collect_incident_evidence(
    scenario: RunScenario,
    run_id: UUID | None = None,
) -> dict[str, object]:
    """Collect only allowlisted evidence for one verified run."""
    repository = _repository()
    run = repository.get(run_id) if run_id else repository.latest(scenario)
    if run.manifest.scenario != scenario:
        raise ValueError("run_id does not belong to the requested scenario")
    if scenario == RunScenario.INDEX_SCAN:
        tools = IndexScanTools(repository)
        evidence = {
            "get_run_summary": tools.get_run_summary(run.manifest.run_id).model_dump(mode="json"),
            "get_query_plan": tools.get_query_plan(run.manifest.run_id).model_dump(mode="json"),
        }
    elif scenario == RunScenario.RACE_CONDITION:
        evidence = {
            "get_concurrency_metrics": RaceConditionTools(repository)
            .get_concurrency_metrics(run.manifest.run_id)
            .model_dump(mode="json")
        }
    else:
        evidence = {
            "get_pool_metrics": PoolExhaustionTools(repository)
            .get_pool_metrics(run.manifest.run_id)
            .model_dump(mode="json")
        }
    return {
        "schema_version": 1,
        "run_id": str(run.manifest.run_id),
        "scenario": scenario.value,
        "evidence": evidence,
    }


@mcp.tool(structured_output=True)
def get_incident_evidence(
    scenario: str,
    run_id: str | None = None,
) -> dict[str, object]:
    """Return verified evidence for index, race, or pool incidents."""
    parsed_scenario = RunScenario(scenario)
    parsed_run_id = UUID(run_id) if run_id else None
    return collect_incident_evidence(parsed_scenario, parsed_run_id)


@mcp.tool(structured_output=True)
def list_incident_scenarios() -> dict[str, list[str]]:
    """List scenario identifiers accepted by get_incident_evidence."""
    return {"scenarios": [item.value for item in RunScenario]}


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
