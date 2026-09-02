from plato_mcp.write_tools import WRITE_TOOL_ANNOTATIONS, executed_result, preview_result


def test_preview_result_is_not_executed():
    result = preview_result({"foo": "bar"}, "Thing")
    assert result.dry_run is True
    assert result.executed is False
    assert result.preview == {"foo": "bar"}
    assert "NOT sent" in result.message
    assert "dry_run=False" in result.message


def test_executed_result_is_executed():
    result = executed_result({"foo": "bar"}, "Thing")
    assert result.dry_run is False
    assert result.executed is True
    assert result.preview == {"foo": "bar"}
    assert result.message == "Thing sent."


def test_write_tool_annotations_marks_destructive_and_non_idempotent():
    assert WRITE_TOOL_ANNOTATIONS.destructive_hint is True
    assert WRITE_TOOL_ANNOTATIONS.idempotent_hint is False
    assert WRITE_TOOL_ANNOTATIONS.read_only_hint is False
