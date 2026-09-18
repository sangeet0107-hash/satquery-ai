from backend.app.models.query import ExecutionStep


def run_vqa(
    query: str,
    image_id: str | None = None,
) -> tuple[str, float, list[ExecutionStep]]:
    trace = [
        ExecutionStep(
            step="VQA specialist initialized",
            status="complete",
        ),
        ExecutionStep(
            step="VQA model execution",
            status="stub",
        ),
    ]

    answer = (
        "The query was successfully routed to the Visual Question "
        "Answering specialist. The real satellite VQA model will be "
        "connected in the next AI-model milestone."
    )

    confidence = 0.50

    return answer, confidence, trace