"""LangChain tool definitions backed by TaskGraph's read-only services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.ai.errors import ToolPlanError
from app.ai.tools.index_scan import IndexScanTools
from app.ai.tools.race_condition import RaceConditionTools


class RunIdInput(BaseModel):
    """Strict argument schema shared by incident-analysis tools."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID = Field(description="UUID of the TaskGraph demonstration run")


class ToolRegistry(Protocol):
    """Minimal registry interface consumed by the graph."""

    @property
    def names(self) -> set[str]: ...

    def openai_definitions(self) -> list[dict[str, Any]]: ...

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class LangChainToolRegistry:
    """Allowlist and execute StructuredTool instances by exact name."""

    _tools: dict[str, Any]

    @property
    def names(self) -> set[str]:
        return set(self._tools)

    def openai_definitions(self) -> list[dict[str, Any]]:
        from langchain_core.utils.function_calling import convert_to_openai_tool

        return [
            convert_to_openai_tool(tool, strict=True) for tool in self._tools.values()
        ]

    def invoke(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolPlanError(f"Unknown or disallowed tool: {name}")
        try:
            result = tool.invoke(arguments)
        except Exception as exc:
            raise ToolPlanError(f"Tool {name} rejected its arguments") from exc
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        if not isinstance(result, dict):
            raise ToolPlanError(f"Tool {name} returned a non-object result")
        return result


def build_index_tool_registry(
    index_tools: IndexScanTools,
    race_tools: RaceConditionTools | None = None,
) -> LangChainToolRegistry:
    """Create two real LangChain tools over verified TaskGraph artifacts."""
    from langchain_core.tools import StructuredTool

    def get_run_summary(run_id: UUID) -> dict[str, Any]:
        """Return measured before/after facts for one TaskGraph run."""
        return index_tools.get_run_summary(run_id).model_dump(mode="json")

    def get_query_plan(run_id: UUID) -> dict[str, Any]:
        """Return verified PostgreSQL plan features for one TaskGraph run."""
        return index_tools.get_query_plan(run_id).model_dump(mode="json")

    tools = [
        StructuredTool.from_function(
            func=get_run_summary,
            name="get_run_summary",
            description=(
                "Get measured dataset size, before/after execution time, speedup, "
                "applied index, and evidence references for a TaskGraph run."
            ),
            args_schema=RunIdInput,
        ),
        StructuredTool.from_function(
            func=get_query_plan,
            name="get_query_plan",
            description=(
                "Get the verified Seq Scan to index-plan transition, query, index "
                "definition, and evidence references for a TaskGraph run."
            ),
            args_schema=RunIdInput,
        ),
    ]
    if race_tools is not None:
        def get_concurrency_metrics(run_id: UUID) -> dict[str, Any]:
            """Return verified lost-update and locking outcomes for one run."""
            return race_tools.get_concurrency_metrics(run_id).model_dump(mode="json")

        tools.append(
            StructuredTool.from_function(
                func=get_concurrency_metrics,
                name="get_concurrency_metrics",
                description=(
                    "Get verified lost-update, pessimistic-lock wait and optimistic "
                    "version-conflict evidence for a TaskGraph race-condition run."
                ),
                args_schema=RunIdInput,
            )
        )
    return LangChainToolRegistry({tool.name: tool for tool in tools})
