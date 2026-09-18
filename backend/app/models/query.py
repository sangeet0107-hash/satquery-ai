from enum import Enum

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


class AnalyzeResponse(BaseModel):
    query: str
    task: TaskType
    answer: str
    confidence: float
    execution_trace: list[ExecutionStep]