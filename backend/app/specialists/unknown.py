from backend.app.models.query import ExecutionStep


def run_unknown(
    query: str,
) -> tuple[str, float, list[ExecutionStep]]:
    trace = [
        ExecutionStep(
            step="No specialist matched the query",
            status="warning",
        ),
    ]

    answer = (
        "I could not confidently determine which satellite-analysis "
        "capability this query requires. Try asking about visible "
        "objects, object locations, changes between images, or SAR data."
    )

    confidence = 0.10

    return answer, confidence, trace