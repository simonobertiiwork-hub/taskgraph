"""One offline-first acceptance check for the complete AI subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from prometheus_client import generate_latest

from app.ai.events import KafkaIncidentPublisher
from app.ai.schemas import IncidentAnalysisResponse
from demos.cases.ai_evals import AIEvalConfig, run_ai_evals
from demos.cases.mcp_smoke import MCPSmokeConfig, run_mcp_smoke
from demos.common.reporting import write_json, write_text


@dataclass(frozen=True, slots=True)
class FinalSmokeConfig:
    dataset_path: Path = Path("demos/evals/incident_cases.json")
    results_dir: Path = Path("demos/results")
    output_dir: Path = Path("demos/results")
    publish_kafka: bool = False
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_topic: str = "taskgraph.ai.incident.completed"


def _latest_analysis(results_dir: Path) -> IncidentAnalysisResponse:
    paths = list((results_dir / "ai_incident_analyst").glob("*/report.json"))
    if not paths:
        raise ValueError("No AI analysis report exists for the Kafka smoke check")
    latest = max(paths, key=lambda path: path.stat().st_mtime)
    return IncidentAnalysisResponse.model_validate_json(latest.read_text(encoding="utf-8"))


async def run_final_smoke(config: FinalSmokeConfig) -> dict[str, object]:
    from app.ai import observability  # noqa: F401 - registers metric families

    eval_result = await run_ai_evals(
        AIEvalConfig(
            dataset_path=config.dataset_path,
            results_dir=config.results_dir,
            output_dir=config.output_dir,
        )
    )
    mcp_result = await run_mcp_smoke(
        MCPSmokeConfig(results_dir=config.results_dir)
    )
    metrics_payload = generate_latest().decode("utf-8")
    metrics_ok = all(
        name in metrics_payload
        for name in (
            "taskgraph_ai_analyses_total",
            "taskgraph_ai_analysis_duration_seconds",
            "taskgraph_ai_tool_calls_total",
            "taskgraph_ai_kafka_events_total",
        )
    )
    kafka_status = "skipped"
    if config.publish_kafka:
        response = _latest_analysis(config.results_dir)
        if response.report is None:
            raise ValueError("Latest AI analysis did not produce a validated report")
        await KafkaIncidentPublisher(
            bootstrap_servers=config.kafka_bootstrap_servers,
            topic=config.kafka_topic,
        ).publish(response, response.report.scenario)
        kafka_status = "published"

    passed = bool(eval_result["passed"] and mcp_result["passed"] and metrics_ok)
    if config.publish_kafka:
        passed = passed and kafka_status == "published"
    summary = {
        "status": "passed" if passed else "failed",
        "offline_eval_cases": eval_result["metrics"]["total_cases"],
        "tool_selection_accuracy_percent": eval_result["metrics"]["tool_selection_accuracy_percent"],
        "grounding_rate_percent": eval_result["metrics"]["grounding_rate_percent"],
        "mcp_stdio_transport": "passed" if mcp_result["passed"] else "failed",
        "prometheus_metrics": "passed" if metrics_ok else "failed",
        "kafka_event": kafka_status,
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    result_dir = config.output_dir.resolve() / "final_smoke" / f"{timestamp}_{uuid4()}"
    result_dir.mkdir(parents=True, exist_ok=False)
    write_json(result_dir / "report.json", summary)
    report_path = result_dir / "report.md"
    write_text(
        report_path,
        "# TaskGraph AI Final Smoke\n\n"
        + "\n".join(f"- {key}: `{value}`" for key, value in summary.items())
        + "\n",
    )
    return {"passed": passed, "summary": summary, "report_path": report_path}
