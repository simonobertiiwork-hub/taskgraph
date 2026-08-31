from pathlib import Path

import pytest

from demos.cases.ai_evals import AIEvalConfig, load_eval_cases, run_ai_evals
from tests.unit.run_artifacts import write_index_run, write_pool_run, write_race_run


DATASET = Path("demos/evals/incident_cases.json")


def test_eval_dataset_has_twenty_unique_cases_and_all_scenarios():
    cases = load_eval_cases(DATASET)
    assert len(cases) == 20
    assert len({case.id for case in cases}) == 20
    assert {case.scenario.value for case in cases} == {
        "index_scan",
        "race_condition",
        "connection_pool_exhaustion",
    }


@pytest.mark.asyncio
async def test_twenty_offline_evals_pass_without_real_llm(tmp_path):
    results = tmp_path / "runs"
    output = tmp_path / "output"
    write_index_run(results)
    write_race_run(results)
    write_pool_run(results)
    actual = await run_ai_evals(
        AIEvalConfig(dataset_path=DATASET, results_dir=results, output_dir=output)
    )
    assert actual["passed"] is True
    assert actual["metrics"] == {
        "total_cases": 20,
        "tool_selection_accuracy_percent": 100.0,
        "completion_rate_percent": 100.0,
        "grounding_rate_percent": 100.0,
        "passed_cases": 20,
    }
