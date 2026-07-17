"""Test that _build_input_data sets input_type='text' for non-audio runs."""

from assemblix_api.api.rest.executions import _build_input_data, _parse_execute_payload


def test_text_run_sets_input_type_text() -> None:
    """Verify that text runs get input_type='text' for CEL conditions."""
    # Arrange
    request = _parse_execute_payload('{"input": {"message": "hi"}}')
    # Act
    input_data = _build_input_data(request, is_debug=False)
    # Assert
    assert input_data["input_type"] == "text"
