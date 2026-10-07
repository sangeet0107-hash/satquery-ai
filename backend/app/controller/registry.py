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

from backend.app.models.params import (
    ChangeParams,
    GroundingParams,
    NoParams,
    SARParams,
    ToolParams,
    VQAParams,
)
from backend.app.models.query import SpecialistResult, TaskType
from backend.app.specialists.change import run_change_detection
from backend.app.specialists.grounding import run_grounding
from backend.app.specialists.sar import run_sar
from backend.app.specialists.unknown import run_unknown
from backend.app.specialists.vqa import run_vqa


# runner(query, image_id, image_id_2, params) -> SpecialistResult
# (the older (answer, confidence, trace) tuple is still accepted).
Runner = Callable[[str, str | None, str | None, Any], Any]

__all__ = [
    "ChangeParams",
    "GroundingParams",
    "NoParams",
    "SARParams",
    "SpecialistResult",
    "ToolParams",
    "ToolSpec",
    "VQAParams",
    "get_tool",
    "list_tools",
    "register_tool",
]


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
        name="owlvit-grounding",
        task=TaskType.GROUNDING,
        description="Open-vocabulary object localisation (bounding boxes).",
        params_model=GroundingParams,
        runner=lambda q, a, b, p: run_grounding(query=q, image_id=a, params=p),
    )
)

register_tool(
    ToolSpec(
        name="change-detection",
        task=TaskType.CHANGE,
        description="Bi-temporal pixel-level change detection (mask + regions).",
        params_model=ChangeParams,
        runner=lambda q, a, b, p: run_change_detection(
            query=q, image_id=a, image_id_2=b, params=p
        ),
    )
)

register_tool(
    ToolSpec(
        name="sar-analysis",
        task=TaskType.SAR,
        description=(
            "SAR water-like surface mapping, bright target detection and "
            "optical-SAR cross-check."
        ),
        params_model=SARParams,
        runner=lambda q, a, b, p: run_sar(
            query=q, image_id=a, image_id_2=b, params=p
        ),
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
