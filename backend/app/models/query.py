from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    VQA = "VQA"
    GROUNDING = "GROUNDING"
    CHANGE = "CHANGE"
    SAR = "SAR"
    UNKNOWN = "UNKNOWN"


class AnalyzeRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language query about the satellite imagery.",
    )

    image_id: str | None = Field(
        default=None,
        description="Identifier of the currently selected image.",
    )

    image_id_2: str | None = Field(
        default=None,
        description="Optional second image for comparison/change analysis.",
    )


class ExecutionStep(BaseModel):
    step: str
    status: str
    tool: str | None = Field(
        default=None,
        description="Model or tool that performed this step, if any.",
    )
    params: dict[str, Any] | None = Field(
        default=None,
        description="Parameters the tool was invoked with.",
    )


class Evidence(BaseModel):
    """Spatial evidence supporting an answer (pixel coordinates)."""

    kind: str = Field(description="'bbox' or 'mask'.")
    label: str | None = None
    # bbox as [x_min, y_min, x_max, y_max] in pixels of the source image.
    bbox: list[float] | None = None
    # Optional path/identifier of a rendered mask image.
    mask_ref: str | None = None
    score: float | None = None


class AnalyzeResponse(BaseModel):
    query: str
    task: TaskType
    answer: str
    confidence: float
    execution_trace: list[ExecutionStep]
    evidence: list[Evidence] = Field(default_factory=list)