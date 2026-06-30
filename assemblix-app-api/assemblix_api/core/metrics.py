"""Prometheus metric definitions for the workflow engine. Single default registry
(multiprocess only when PROMETHEUS_MULTIPROC_DIR is set, handled by prometheus-client)."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Custom buckets scaled to minute-range workflow durations (seconds).
_DURATION_BUCKETS = (0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800)

workflow_executions_total = Counter(
    "assemblix_workflow_executions_total",
    "Workflow executions by terminal status.",
    ["status"],
)
workflow_execution_duration_seconds = Histogram(
    "assemblix_workflow_execution_duration_seconds",
    "Wall-clock execution duration.",
    buckets=_DURATION_BUCKETS,
)
workflow_steps_total = Counter(
    "assemblix_workflow_steps_total",
    "Node steps executed.",
    ["node_type", "status"],
)
nodes_in_progress = Gauge(
    "assemblix_nodes_in_progress",
    "Nodes currently executing.",
    multiprocess_mode="livesum",
)
llm_tokens_total = Counter(
    "assemblix_llm_tokens_total",
    "LLM tokens consumed.",
    ["model"],
)
llm_cost_usd_total = Counter(
    "assemblix_llm_cost_usd_total",
    "LLM cost in USD.",
)
queue_depth = Gauge(
    "assemblix_queue_depth",
    "Pending jobs in the execution queue.",
)


def observe_execution(status: str, duration_seconds: float) -> None:
    """Record a completed workflow execution with its terminal status and wall-clock duration."""
    workflow_executions_total.labels(status=status).inc()
    workflow_execution_duration_seconds.observe(max(0.0, duration_seconds))


def observe_step(node_type: str, status: str) -> None:
    """Record a single node step completion."""
    workflow_steps_total.labels(node_type=node_type, status=status).inc()


def track_llm(model: str | None, tokens: int | None, cost_usd: float | None) -> None:
    """Record LLM token consumption and cost for a single inference call."""
    if tokens:
        llm_tokens_total.labels(model=model or "unknown").inc(tokens)
    if cost_usd:
        llm_cost_usd_total.inc(cost_usd)


def set_nodes_in_progress(delta: int) -> None:
    """Adjust the in-progress node gauge by delta (positive = start, negative = finish)."""
    nodes_in_progress.inc(delta)


def set_queue_depth(n: int) -> None:
    """Set the current execution queue depth to an absolute value."""
    queue_depth.set(n)


def render_latest() -> str:
    """Return the current Prometheus exposition text for the default registry."""
    return generate_latest().decode()


# Content-Type header value for the /metrics endpoint.
CONTENT_TYPE = CONTENT_TYPE_LATEST
