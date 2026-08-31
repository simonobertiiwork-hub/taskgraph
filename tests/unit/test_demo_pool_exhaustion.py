from demos.cases.pool_exhaustion import PoolExhaustionConfig, build_pool_summary


def phase(pool_size: int, completed: int, timeouts: int):
    return {
        "pool_size": pool_size,
        "max_overflow": 0,
        "pool_timeout_seconds": 0.2,
        "concurrency": 5,
        "hold_seconds": 0.35,
        "completed_requests": completed,
        "pool_timeouts": timeouts,
        "failure_rate_percent": timeouts / 5 * 100,
        "elapsed_ms": 360.0,
        "requests": [],
    }


def test_pool_summary_requires_same_load_and_removes_timeouts():
    summary = build_pool_summary(phase(2, 2, 3), phase(5, 5, 0))
    assert summary["status"] == "passed"
    assert summary["comparison"]["timeouts_removed"] == 3


def test_pool_config_rejects_timeout_longer_than_hold():
    config = PoolExhaustionConfig(hold_seconds=0.2, pool_timeout_seconds=0.3)
    try:
        config.validate()
    except ValueError as error:
        assert "lower than hold-seconds" in str(error)
    else:
        raise AssertionError("invalid config was accepted")

