import pytest

from demos.cases.index_scan import (
    INDEX_NAME,
    IndexScanConfig,
    build_summary,
    normalize_explain_payload,
    plan_index_names,
    plan_node_types,
    summarize_plans,
)


def make_explain(
    node_type: str,
    execution_time: float,
    *,
    planning_time: float = 0.05,
    index_name: str | None = None,
    child: dict | None = None,
) -> dict:
    plan = {"Node Type": node_type}
    if index_name is not None:
        plan["Index Name"] = index_name
    if child is not None:
        plan["Plans"] = [child]
    return {
        "Plan": plan,
        "Planning Time": planning_time,
        "Execution Time": execution_time,
    }


def test_normalize_explain_payload_accepts_json_string():
    raw = '[{"Plan":{"Node Type":"Seq Scan"},"Planning Time":0.1,"Execution Time":2.0}]'

    normalized = normalize_explain_payload(raw)

    assert normalized["Plan"]["Node Type"] == "Seq Scan"


def test_normalize_explain_payload_rejects_unknown_shape():
    with pytest.raises(ValueError, match="Unexpected PostgreSQL EXPLAIN"):
        normalize_explain_payload([])


def test_plan_helpers_walk_nested_bitmap_index_plan():
    explain = make_explain(
        "Bitmap Heap Scan",
        0.2,
        child={
            "Node Type": "Bitmap Index Scan",
            "Index Name": INDEX_NAME,
        },
    )

    assert plan_node_types(explain) == ["Bitmap Heap Scan", "Bitmap Index Scan"]
    assert plan_index_names(explain) == [INDEX_NAME]


def test_summarize_plans_uses_median_instead_of_single_run():
    plans = [
        make_explain("Seq Scan", 14.0),
        make_explain("Seq Scan", 12.0),
        make_explain("Seq Scan", 80.0),
    ]

    summary = summarize_plans(plans)

    assert summary["median_execution_time_ms"] == 14.0
    assert summary["node_types"] == ["Seq Scan"]


def test_build_summary_passes_for_expected_transition():
    before = [make_explain("Seq Scan", value) for value in (14.0, 13.0, 15.0)]
    after = [
        make_explain("Index Scan", value, index_name=INDEX_NAME)
        for value in (0.08, 0.07, 0.09)
    ]

    summary = build_summary(before, after)

    assert summary["status"] == "passed"
    assert all(summary["verification"].values())
    assert summary["comparison"]["speedup"] == pytest.approx(175.0)


def test_build_summary_fails_when_post_change_plan_is_sequential():
    before = [make_explain("Seq Scan", 14.0)]
    after = [make_explain("Seq Scan", 13.0)]

    summary = build_summary(before, after)

    assert summary["status"] == "failed"
    assert summary["verification"]["after_uses_index_plan"] is False


@pytest.mark.parametrize(
    ("config", "message"),
    [
        (IndexScanConfig(rows=0), "rows"),
        (IndexScanConfig(rows=10, target=11), "target"),
        (IndexScanConfig(runs=0), "runs"),
    ],
)
def test_config_validation(config, message):
    with pytest.raises(ValueError, match=message):
        config.validate()
