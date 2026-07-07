"""Unit tests for threading the request-level stream flag into the executor input_data."""

from assemblix_api.api.rest.executions import _build_input_data
from assemblix_api.dto.requests.execution import ExecuteWorkflowRequest


def test_build_input_data_threads_stream_flag() -> None:
    """request.stream=True lands in the executor input_data bag."""
    # Arrange
    request = ExecuteWorkflowRequest(input={"message": "hi"}, stream=True, task=True)

    # Act
    input_data = _build_input_data(request, is_debug=False)

    # Assert
    assert input_data["stream"] is True


def test_build_input_data_omits_stream_when_false() -> None:
    """Default (stream=False) adds no stream key — non-streaming runs stay byte-for-byte the same."""
    # Arrange
    request = ExecuteWorkflowRequest(input={"message": "hi"})

    # Act
    input_data = _build_input_data(request, is_debug=False)

    # Assert
    assert "stream" not in input_data
