from backend.app.controller.classifier import classify_query
from backend.app.models.query import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExecutionStep,
    TaskType,
)
from backend.app.specialists.change import run_change_detection
from backend.app.specialists.grounding import run_grounding
from backend.app.specialists.sar import run_sar
from backend.app.specialists.unknown import run_unknown
from backend.app.specialists.vqa import run_vqa


def analyze_query(request: AnalyzeRequest) -> AnalyzeResponse:
    trace: list[ExecutionStep] = [
        ExecutionStep(
            step="Query received by controller",
            status="complete",
        )
    ]

    task = classify_query(request.query)

    trace.append(
        ExecutionStep(
            step=f"Query classified as {task.value}",
            status="complete",
        )
    )

    if task == TaskType.VQA:
        answer, confidence, specialist_trace = run_vqa(
            query=request.query,
            image_id=request.image_id,
        )

    elif task == TaskType.GROUNDING:
        answer, confidence, specialist_trace = run_grounding(
            query=request.query,
            image_id=request.image_id,
        )

    elif task == TaskType.CHANGE:
        answer, confidence, specialist_trace = run_change_detection(
            query=request.query,
            image_id=request.image_id,
            image_id_2=request.image_id_2,
        )

    elif task == TaskType.SAR:
        answer, confidence, specialist_trace = run_sar(
            query=request.query,
            image_id=request.image_id,
            image_id_2=request.image_id_2,
        )

    else:
        answer, confidence, specialist_trace = run_unknown(
            query=request.query,
        )

    trace.append(
        ExecutionStep(
            step=f"Routed request to {task.value} specialist",
            status="complete",
        )
    )

    trace.extend(specialist_trace)

    return AnalyzeResponse(
        query=request.query,
        task=task,
        answer=answer,
        confidence=confidence,
        execution_trace=trace,
    )