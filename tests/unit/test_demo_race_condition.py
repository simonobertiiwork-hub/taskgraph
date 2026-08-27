import pytest

from demos.cases.race_condition import (
    ORIGINAL_TITLE,
    TASK_A_TITLE,
    TASK_B_TITLE,
    RaceConditionConfig,
    build_race_summary,
)


def make_successful_scenarios():
    last_write_wins = {
        "transaction_a_backend_pid": 101,
        "transaction_b_backend_pid": 102,
        "transaction_a_read": {"title": ORIGINAL_TITLE, "version": 1},
        "transaction_b_read": {"title": ORIGINAL_TITLE, "version": 1},
        "final": {"title": TASK_B_TITLE, "version": 1},
    }
    pessimistic_lock = {
        "configured_hold_seconds": 1.0,
        "transaction_a": {"backend_pid": 103},
        "transaction_b": {
            "backend_pid": 104,
            "observed_after_lock": {"title": TASK_A_TITLE, "version": 1},
            "lock_wait_seconds": 0.95,
        },
        "final": {"title": TASK_B_TITLE, "version": 1},
    }
    optimistic_lock = {
        "transaction_a_backend_pid": 105,
        "transaction_b_backend_pid": 106,
        "transaction_a_rows_updated": 1,
        "transaction_b_rows_updated": 0,
        "transaction_b_conflict_detected": True,
        "final": {"title": TASK_A_TITLE, "version": 2},
    }
    return last_write_wins, pessimistic_lock, optimistic_lock


def test_build_race_summary_passes_for_expected_outcomes():
    summary = build_race_summary(*make_successful_scenarios())

    assert summary["status"] == "passed"
    assert all(
        value
        for checks in summary["verification"].values()
        for value in checks.values()
    )


def test_build_race_summary_fails_when_stale_writer_is_not_rejected():
    scenarios = list(make_successful_scenarios())
    scenarios[2]["transaction_b_rows_updated"] = 1
    scenarios[2]["transaction_b_conflict_detected"] = False
    scenarios[2]["final"] = {"title": TASK_B_TITLE, "version": 2}

    summary = build_race_summary(*scenarios)

    assert summary["status"] == "failed"
    assert (
        summary["verification"]["optimistic_lock"][
            "stale_second_writer_updated_no_rows"
        ]
        is False
    )


@pytest.mark.parametrize("hold_seconds", [0, 0.09, 10.01])
def test_config_rejects_unsafe_hold_interval(hold_seconds):
    with pytest.raises(ValueError, match="hold-seconds"):
        RaceConditionConfig(hold_seconds=hold_seconds).validate()


@pytest.mark.parametrize("hold_seconds", [0.1, 1.0, 10.0])
def test_config_accepts_supported_hold_interval(hold_seconds):
    RaceConditionConfig(hold_seconds=hold_seconds).validate()
