"""
Pure (no-DB, no-async) helpers that derive a crash-resume position from a list
of persisted ExecutionStep records.

Usage (by the executor, Task E2):
    steps: list[ExecutionStep] = await repo.get_steps(execution_id)
    rp = find_resume_point(steps)
    if rp is None:
        # No completed steps — start fresh from the START node.
        ...
    else:
        # Resume from rp.last_node_id with rp.state as the workflow state.
        ...

NOTE on project_state:
    ExecutionStep stores state_after (the workflow state dict) but has NO
    project_state column.  project_state is NOT checkpointed per-step; on
    resume the caller must reload it from the ClientSession (the live DB row).
    Both functions return project_state={} as a signal to the caller: fill it
    yourself before continuing execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from assemblix_api.enums import NodeType, StepStatus

if TYPE_CHECKING:
    from assemblix_api.database.models.execution_step import ExecutionStep


@dataclass(frozen=True)
class ResumePoint:
    """Crash-resume position derived from persisted execution steps.

    Attributes:
        last_node_id:     node_id of the last successfully completed step.
        next_step_number: step_number to assign to the next new step (last + 1).
        state:            workflow state dict as it stood after the last completed
                          step (from ExecutionStep.state_after).
        project_state:    always {} — ExecutionStep has no project_state column;
                          the caller reloads this from ClientSession before resuming.
        condition_index:  for CONDITION nodes, the branch index that was chosen
                          (from output_data["condition_index"]); None for all other
                          node types.  Used by GraphNavigator to pick the right edge.
        last_output:      output_data of the last completed step, passed as
                          previous_output to the first resumed node so it receives
                          the correct input from its predecessor.
    """

    last_node_id: str
    next_step_number: int
    state: dict
    project_state: dict
    condition_index: int | None
    last_output: dict | None = None


def find_resume_point(steps: list[ExecutionStep]) -> ResumePoint | None:
    """Return the resume position for a crashed execution, or None to start fresh.

    Only COMPLETED steps are considered; a trailing FAILED or RUNNING step is
    ignored (it never produced valid output).  The step with the highest
    step_number is chosen — the input list need not be sorted.

    Args:
        steps: All ExecutionStep records for the execution (any order, any status).

    Returns:
        ResumePoint built from the last completed step, or None if there are no
        completed steps (caller should start execution from the START node).
    """
    completed = [s for s in steps if s.status == StepStatus.COMPLETED]
    if not completed:
        return None

    last = max(completed, key=lambda s: s.step_number)

    condition_index: int | None = None
    if last.node_type == NodeType.CONDITION:
        raw = (last.output_data or {}).get("condition_index")
        condition_index = int(raw) if raw is not None else None

    return ResumePoint(
        last_node_id=last.node_id,
        next_step_number=last.step_number + 1,
        state=last.state_after or {},
        project_state={},  # NOT stored per-step; caller reloads from ClientSession
        condition_index=condition_index,
        last_output=last.output_data or None,
    )


def rebuild_state(steps: list[ExecutionStep]) -> tuple[dict, dict]:
    """Reconstruct (state, project_state) from the last completed step.

    state       — workflow variable dict from the last completed step's state_after.
    project_state — always {}; ExecutionStep has no project_state column.  On
                    resume the caller must reload project_state from the live
                    ClientSession row before continuing execution.

    Args:
        steps: All ExecutionStep records for the execution (any order, any status).

    Returns:
        (state, project_state) tuple.  Both are plain dicts; project_state is
        always empty — the caller is responsible for repopulating it.
    """
    rp = find_resume_point(steps)
    if rp is None:
        return {}, {}
    return rp.state, rp.project_state
