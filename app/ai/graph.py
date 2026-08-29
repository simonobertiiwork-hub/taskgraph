"""LangGraph workflow for grounded analysis of one index-scan run."""

from __future__ import annotations

import time
from typing import Any, Literal, TypedDict
from uuid import UUID, uuid4

from pydantic import ValidationError as PydanticValidationError

from app.ai.errors import AIIncidentError, ToolPlanError
from app.ai.prompts import (
    build_repair_messages,
    build_report_messages,
    build_tool_planning_messages,
)
from app.ai.provider import LLMCompletion, LLMProvider, strip_markdown_fence
from app.ai.reporting import build_grounded_incident_report
from app.ai.rag.service import DocumentRetriever
from app.ai.rag.schemas import RetrievedChunk
from app.ai.repositories.runs import FileRunRepository, RunRepositoryError
from app.ai.schemas import (
    ExecutedToolCall,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentAnalysisStatus,
    IncidentReportDraft,
    ProviderCallRecord,
    RequestedToolCall,
    RunScenario,
)
from app.ai.tool_registry import ToolRegistry
from app.ai.validation import REQUIRED_TOOLS, required_tools_for, validate_incident_report

MAX_PLAN_ATTEMPTS = 2
MAX_TOOL_CALLS = 4


class AnalysisState(TypedDict, total=False):
    """State passed between deterministic and model-backed graph nodes."""

    analysis_id: UUID
    request: IncidentAnalysisRequest
    scenario: RunScenario
    plan_attempts: int
    repair_attempts: int
    pending_tool_calls: list[RequestedToolCall]
    tool_results: dict[str, dict[str, Any]]
    tool_calls: list[ExecutedToolCall]
    provider_calls: list[ProviderCallRecord]
    missing_tools: list[str]
    plan_errors: list[str]
    raw_report: str
    draft_report: IncidentReportDraft | None
    validation_errors: list[str]
    fatal_error: str | None
    retrieved_documents: list[RetrievedChunk]


class IncidentWorkflow:
    """Node implementation kept separate so every policy is unit-testable."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        tool_registry: ToolRegistry,
        repository: FileRunRepository,
        deterministic_report: bool = False,
        retriever: DocumentRetriever | None = None,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.repository = repository
        self.deterministic_report = deterministic_report
        self.retriever = retriever

    async def validate_request_node(self, state: AnalysisState) -> dict[str, Any]:
        request = state["request"]
        try:
            run = self.repository.get(request.run_id)
        except RunRepositoryError as exc:
            return {"fatal_error": str(exc), "validation_errors": [str(exc)]}
        if run.manifest.scenario not in {RunScenario.INDEX_SCAN, RunScenario.RACE_CONDITION}:
            message = (
                f"Run {request.run_id} is {run.manifest.scenario.value}; "
                "this workflow supports index_scan and race_condition"
            )
            return {"fatal_error": message, "validation_errors": [message]}
        return {
            "scenario": run.manifest.scenario,
            "missing_tools": sorted(required_tools_for(run.manifest.scenario)),
            "fatal_error": None,
        }

    async def plan_tools_node(self, state: AnalysisState) -> dict[str, Any]:
        if state.get("fatal_error"):
            return {}
        request = state["request"]
        results = state.get("tool_results", {})
        scenario = state["scenario"]
        missing = sorted(required_tools_for(scenario) - set(results))
        attempt = state.get("plan_attempts", 0) + 1
        messages = build_tool_planning_messages(
            request,
            scenario=scenario.value,
            missing_tools=missing,
            previous_errors=state.get("plan_errors", []),
        )
        started = time.perf_counter()
        allowed = required_tools_for(scenario)
        tool_definitions = [
            item
            for item in self.tool_registry.openai_definitions()
            if item.get("function", {}).get("name") in allowed
        ]
        try:
            completion = await self.provider.choose_tools(
                messages=messages,
                tools=tool_definitions,
            )
        except AIIncidentError as exc:
            return {
                "plan_attempts": attempt,
                "pending_tool_calls": [],
                "fatal_error": str(exc),
                "validation_errors": [str(exc)],
            }
        latency_ms = (time.perf_counter() - started) * 1_000
        return {
            "plan_attempts": attempt,
            "pending_tool_calls": list(completion.tool_calls),
            "provider_calls": state.get("provider_calls", [])
            + [self._provider_record("tool_planning", completion, latency_ms)],
            "plan_errors": [],
        }

    async def execute_tools_node(self, state: AnalysisState) -> dict[str, Any]:
        if state.get("fatal_error"):
            return {}
        request = state["request"]
        results = dict(state.get("tool_results", {}))
        executed = list(state.get("tool_calls", []))
        errors: list[str] = []

        for call in state.get("pending_tool_calls", []):
            if len(executed) >= MAX_TOOL_CALLS:
                errors.append(f"Tool-call limit {MAX_TOOL_CALLS} exceeded")
                break
            if call.tool_name in results:
                continue
            if call.tool_name not in self.tool_registry.names:
                errors.append(f"Unknown or disallowed tool: {call.tool_name}")
                continue
            if call.tool_name not in required_tools_for(
                state.get("scenario", RunScenario.INDEX_SCAN)
            ):
                errors.append(f"Tool is not allowed for this scenario: {call.tool_name}")
                continue
            try:
                argument_run_id = UUID(str(call.arguments.get("run_id")))
            except (TypeError, ValueError, AttributeError):
                errors.append(f"{call.tool_name} has an invalid run_id")
                continue
            if argument_run_id != request.run_id:
                errors.append(f"{call.tool_name} attempted to access another run_id")
                continue

            started = time.perf_counter()
            try:
                result = self.tool_registry.invoke(call.tool_name, call.arguments)
            except ToolPlanError as exc:
                errors.append(str(exc))
                continue
            latency_ms = (time.perf_counter() - started) * 1_000
            results[call.tool_name] = result
            executed.append(
                ExecutedToolCall(
                    call_id=call.call_id,
                    tool_name=call.tool_name,
                    arguments=call.arguments,
                    result=result,
                    latency_ms=round(latency_ms, 3),
                )
            )

        missing = sorted(
            required_tools_for(state.get("scenario", RunScenario.INDEX_SCAN))
            - set(results)
        )
        validation_errors: list[str] = []
        if missing and state.get("plan_attempts", 0) >= MAX_PLAN_ATTEMPTS:
            validation_errors.append(
                f"Model did not select required tools: {', '.join(missing)}"
            )
        elif errors and not missing:
            validation_errors.extend(errors)
        return {
            "tool_results": results,
            "tool_calls": executed,
            "missing_tools": missing,
            "plan_errors": errors,
            "validation_errors": validation_errors,
        }

    async def generate_report_node(self, state: AnalysisState) -> dict[str, Any]:
        if state.get("fatal_error") or state.get("missing_tools"):
            return {}
        if self.deterministic_report:
            try:
                draft = build_grounded_incident_report(
                    state["request"], state["tool_results"], state.get("retrieved_documents", [])
                )
            except AIIncidentError as exc:
                return {
                    "fatal_error": str(exc),
                    "validation_errors": [str(exc)],
                }
            return {
                "raw_report": draft.model_dump_json(),
                "draft_report": draft,
                "validation_errors": [],
            }
        messages = build_report_messages(state["request"], state["tool_results"])
        return await self._request_report(
            state,
            messages=messages,
            purpose="report",
            repair_attempts=state.get("repair_attempts", 0),
        )

    async def validate_report_node(self, state: AnalysisState) -> dict[str, Any]:
        draft = state.get("draft_report")
        if draft is None:
            return {"validation_errors": state.get("validation_errors", [])}
        errors = validate_incident_report(
            draft,
            state["request"],
            state["tool_results"],
            state.get("retrieved_documents", []),
        )
        return {"validation_errors": errors}

    async def retrieve_documents_node(self, state: AnalysisState) -> dict[str, Any]:
        if state.get("fatal_error") or self.retriever is None:
            return {"retrieved_documents": []}
        try:
            documents = await self.retriever.search(
                state["request"].question, state["scenario"]
            )
        except Exception:
            documents = []
        return {"retrieved_documents": documents}

    async def repair_report_node(self, state: AnalysisState) -> dict[str, Any]:
        messages = build_repair_messages(
            state["request"],
            tool_results=state["tool_results"],
            previous_output=state.get("raw_report", ""),
            validation_errors=state.get("validation_errors", []),
        )
        attempts = state.get("repair_attempts", 0) + 1
        return await self._request_report(
            state,
            messages=messages,
            purpose="repair",
            repair_attempts=attempts,
        )

    async def _request_report(
        self,
        state: AnalysisState,
        *,
        messages: list[dict[str, str]],
        purpose: Literal["report", "repair"],
        repair_attempts: int,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            completion = await self.provider.complete_json(
                messages=messages,
                json_schema=IncidentReportDraft.model_json_schema(),
                schema_name="index_incident_report",
            )
        except AIIncidentError as exc:
            return {
                "fatal_error": str(exc),
                "validation_errors": [str(exc)],
                "repair_attempts": repair_attempts,
            }
        latency_ms = (time.perf_counter() - started) * 1_000
        raw = completion.content or ""
        provider_calls = state.get("provider_calls", []) + [
            self._provider_record(purpose, completion, latency_ms)
        ]
        try:
            draft = IncidentReportDraft.model_validate_json(strip_markdown_fence(raw))
            errors: list[str] = []
        except PydanticValidationError as exc:
            draft = None
            errors = [
                "Structured report does not satisfy schema: "
                + "; ".join(
                    f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                    for item in exc.errors()[:8]
                )
            ]
        return {
            "raw_report": raw,
            "draft_report": draft,
            "validation_errors": errors,
            "repair_attempts": repair_attempts,
            "provider_calls": provider_calls,
        }

    @staticmethod
    def _provider_record(
        purpose: Literal["tool_planning", "report", "repair"],
        completion: LLMCompletion,
        latency_ms: float,
    ) -> ProviderCallRecord:
        return ProviderCallRecord(
            purpose=purpose,
            provider=completion.provider,
            model=completion.model,
            attempts=completion.attempts,
            latency_ms=round(latency_ms, 3),
            provider_request_id=completion.provider_request_id,
            usage=completion.usage,
        )

    @staticmethod
    def route_after_tools(
        state: AnalysisState,
    ) -> Literal["plan_tools", "retrieve_documents", "end"]:
        if state.get("fatal_error") or state.get("validation_errors"):
            return "end"
        if state.get("missing_tools"):
            if state.get("plan_attempts", 0) < MAX_PLAN_ATTEMPTS:
                return "plan_tools"
            return "end"
        return "retrieve_documents"

    @staticmethod
    def route_after_validation(
        state: AnalysisState,
    ) -> Literal["repair_report", "end"]:
        if state.get("fatal_error"):
            return "end"
        if state.get("validation_errors") and state.get("repair_attempts", 0) < 1:
            return "repair_report"
        return "end"

    def compile(self) -> Any:
        """Compile the real LangGraph with two bounded conditional loops."""
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is not installed; install project requirements"
            ) from exc

        builder = StateGraph(AnalysisState)
        builder.add_node("validate_request", self.validate_request_node)
        builder.add_node("plan_tools", self.plan_tools_node)
        builder.add_node("execute_tools", self.execute_tools_node)
        builder.add_node("generate_report", self.generate_report_node)
        builder.add_node("retrieve_documents", self.retrieve_documents_node)
        builder.add_node("validate_report", self.validate_report_node)
        builder.add_node("repair_report", self.repair_report_node)
        builder.add_edge(START, "validate_request")
        builder.add_edge("validate_request", "plan_tools")
        builder.add_edge("plan_tools", "execute_tools")
        builder.add_conditional_edges(
            "execute_tools",
            self.route_after_tools,
            {
                "plan_tools": "plan_tools",
                "retrieve_documents": "retrieve_documents",
                "end": END,
            },
        )
        builder.add_edge("retrieve_documents", "generate_report")
        builder.add_edge("generate_report", "validate_report")
        builder.add_conditional_edges(
            "validate_report",
            self.route_after_validation,
            {"repair_report": "repair_report", "end": END},
        )
        builder.add_edge("repair_report", "validate_report")
        return builder.compile()

    async def analyze(
        self, request: IncidentAnalysisRequest
    ) -> IncidentAnalysisResponse:
        """Run the compiled graph and expose only a validated final report."""
        analysis_id = uuid4()
        started = time.perf_counter()
        graph = self.compile()
        final: AnalysisState = await graph.ainvoke(
            {
                "analysis_id": analysis_id,
                "request": request,
                "plan_attempts": 0,
                "repair_attempts": 0,
                "tool_results": {},
                "tool_calls": [],
                "provider_calls": [],
                "missing_tools": sorted(REQUIRED_TOOLS),
                "plan_errors": [],
                "validation_errors": [],
                "fatal_error": None,
                "retrieved_documents": [],
            }
        )
        errors = final.get("validation_errors", [])
        draft = final.get("draft_report")
        completed = draft is not None and not errors and not final.get("fatal_error")
        return IncidentAnalysisResponse(
            analysis_id=analysis_id,
            request=request,
            status=(
                IncidentAnalysisStatus.COMPLETED
                if completed
                else IncidentAnalysisStatus.FAILED
            ),
            report=draft if completed else None,
            tool_calls=final.get("tool_calls", []),
            provider_calls=final.get("provider_calls", []),
            validation_errors=errors,
            latency_ms=round((time.perf_counter() - started) * 1_000, 3),
        )
