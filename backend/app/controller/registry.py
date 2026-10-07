"""
Tool registry (proposal section 5.2).

Every specialist is described by a ToolSpec: what task it serves, which
parameters the controller is allowed to set (a strict Pydantic model), and
how to run it. The controller only ever calls tools through this registry,
so adding a new specialist means registering one more ToolSpec; the
controller itself does not change.
"""

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.query import ExecutionStep, TaskType
from backend.app.specialists.change import run_change_detection
from backend.app.specialists.grounding import run_grounding
from backend.app.specialists.sar import run_sar
from backend.app.specialists.unknown import run_unknown
from backend.app.specialists.vqa import run_vqa


class ToolParams(BaseModel):
    """Base for tool parameters. Unknown parameters are rejected."""

    model_config = ConfigDict(extra="forbid")


class NoParams(ToolParams):
    pass


class VQAParams(ToolParams):
    max_new_tokens: int = Field(default=30, ge=1, le=100)


ToolResult = tuple[str, float, list[ExecutionStep]]

# runner(query, image_id, image_id_2, params) -> (answer, confidence, trace)
Runner = Callable[[str, str | None, str | None, Any], ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    task: TaskType
    description: str
    params_model: type[ToolParams]
    runner: Runner

    def build_params(self, overrides: dict[str, Any] | None = None) -> ToolParams:
        """Validate controller-supplied parameters against the schema."""

        return self.params_model(**(overrides or {}))


_REGISTRY: dict[TaskType, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> ToolSpec:
    if spec.task in _REGISTRY:
        raise ValueError(f"A tool is already registered for {spec.task.value}")

    _REGISTRY[spec.task] = spec
    return spec


def get_tool(task: TaskType) -> ToolSpec:
    return _REGISTRY[task]


def list_tools() -> list[ToolSpec]:
    return list(_REGISTRY.values())


register_tool(
    ToolSpec(
        name="blip-vqa",
        task=TaskType.VQA,
        description="Visual question answering and scene description.",
        params_model=VQAParams,
        runner=lambda q, a, b, p: run_vqa(
            query=q, image_id=a, max_new_tokens=p.max_new_tokens
        ),
    )
)

register_tool(
    ToolSpec(
        name="grounding",
        task=TaskType.GROUNDING,
        description="Region-level object localisation (boxes/masks).",
        params_model=NoParams,
        runner=lambda q, a, b, p: run_grounding(query=q, image_id=a),
    )
)

register_tool(
    ToolSpec(
        name="change-detection",
        task=TaskType.CHANGE,
        description="Bi-temporal change understanding.",
        params_model=NoParams,
        runner=lambda q, a, b, p: run_change_detection(
            query=q, image_id=a, image_id_2=b
        ),
    )
)

register_tool(
    ToolSpec(
        name="sar-fusion",
        task=TaskType.SAR,
        description="SAR interpretation and optical-SAR fusion.",
        params_model=NoParams,
        runner=lambda q, a, b, p: run_sar(query=q, image_id=a, image_id_2=b),
    )
)

register_tool(
    ToolSpec(
        name="no-op",
        task=TaskType.UNKNOWN,
        description="Fallback when no capability matches the query.",
        params_model=NoParams,
        runner=lambda q, a, b, p: run_unknown(query=q),
    )
)
