import pytest

from demos.cases.index_scan import IndexScanConfig


def test_default_config_is_valid():
    config = IndexScanConfig()

    config.validate()


@pytest.mark.parametrize(
    ("config", "expected_message"),
    [
        (
            IndexScanConfig(rows=0),
            "rows",
        ),
        (
            IndexScanConfig(
                rows=10,
                target=11,
            ),
            "target",
        ),
        (
            IndexScanConfig(runs=0),
            "runs",
        ),
    ],
)
def test_invalid_config(
    config: IndexScanConfig,
    expected_message: str,
):
    with pytest.raises(
        ValueError,
        match=expected_message,
    ):
        config.validate()