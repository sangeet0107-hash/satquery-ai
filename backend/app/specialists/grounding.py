from backend.app.models.query import ExecutionStep


def run_grounding(
    query: str,
    image_id: str | None = None,
) -> tuple[str, float, list[ExecutionStep]]:
    trace = [
        ExecutionStep(
            step="Grounding specialist initialized",
            status="complete",
        ),
        ExecutionStep(
            step="Object localization model execution",
            status="stub",
        ),
    ]

    answer = (
        "The query was successfully routed to the Visual Grounding "
        "specialist. Object coordinates and bounding boxes will be "
        "generated once the grounding model is connected."
    )

    confidence = 0.50

    return answer, confidence, trace