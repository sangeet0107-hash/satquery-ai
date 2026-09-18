from backend.app.models.query import ExecutionStep


def run_change_detection(
    query: str,
    image_id: str | None = None,
    image_id_2: str | None = None,
) -> tuple[str, float, list[ExecutionStep]]:
    trace = [
        ExecutionStep(
            step="Change detection specialist initialized",
            status="complete",
        ),
        ExecutionStep(
            step="Multi-temporal image comparison",
            status="stub",
        ),
    ]

    if image_id_2 is None:
        answer = (
            "The query was routed to the Change Detection specialist, "
            "but a second image has not been supplied yet."
        )
        confidence = 0.30
    else:
        answer = (
            "The query was successfully routed to the Change Detection "
            "specialist. Pixel-level and semantic change analysis will "
            "be performed once the change detection model is connected."
        )
        confidence = 0.50

    return answer, confidence, trace