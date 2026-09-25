from uuid import UUID

from assemblix_api.services.notifications.dispatcher import (
    ExecutionFailurePayload,
    NotificationDispatcher,
)

PROJECT_ID = UUID("11111111-1111-1111-1111-111111111111")
WORKFLOW_ID = UUID("22222222-2222-2222-2222-222222222222")
EXECUTION_ID = UUID("33333333-3333-3333-3333-333333333333")


def _payload() -> ExecutionFailurePayload:
    return ExecutionFailurePayload(
        project_id=PROJECT_ID,
        execution_id=EXECUTION_ID,
        workflow_id=WORKFLOW_ID,
        workflow_name="Проверка <ОС>",
        error_type="runtime",
        error_message="boom",
        failed_node_id="node-1",
    )


def test_render_message_links_workflow_and_execution() -> None:
    message = NotificationDispatcher._render_message(_payload(), app_url="https://app.example.com/")

    workflow_url = f"https://app.example.com/projects/{PROJECT_ID}/workflows/{WORKFLOW_ID}"
    execution_url = f"{workflow_url}/executions/{EXECUTION_ID}"
    assert f'<a href="{workflow_url}">Проверка &lt;ОС&gt;</a>' in message
    assert f'<a href="{execution_url}">{EXECUTION_ID}</a>' in message


def test_render_message_without_app_url_falls_back_to_plain_text() -> None:
    message = NotificationDispatcher._render_message(_payload(), app_url="")

    assert "<a href" not in message
    assert "Проверка &lt;ОС&gt;" in message
    assert f"<code>{EXECUTION_ID}</code>" in message
