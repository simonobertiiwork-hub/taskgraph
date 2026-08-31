import importlib.util
from pathlib import Path

import pytest

from app.ai.repositories.runs import FileRunRepository
from app.ai.tool_registry import build_index_tool_registry
from app.ai.tools.index_scan import IndexScanTools
from tests.unit.run_artifacts import write_index_run


def test_langchain_registry_exports_and_executes_strict_tools(tmp_path: Path):
    if importlib.util.find_spec("langchain_core") is None:
        pytest.skip("langchain-core is unavailable in the isolated test runtime")

    context = write_index_run(tmp_path)
    registry = build_index_tool_registry(IndexScanTools(FileRunRepository(tmp_path)))

    definitions = registry.openai_definitions()
    result = registry.invoke(
        "get_run_summary",
        {"run_id": str(context.run_id)},
    )

    assert registry.names == {"get_run_summary", "get_query_plan"}
    assert {item["function"]["name"] for item in definitions} == registry.names
    assert result["run_id"] == str(context.run_id)
    assert result["dataset_rows"] == 200_000
