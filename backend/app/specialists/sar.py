from backend.app.models.query import ExecutionStep


def run_sar(
    query: str,
    image_id: str | None = None,
    image_id_2: str | None = None,
) -> tuple[str, float, list[ExecutionStep]]:
    trace = [
        ExecutionStep(
            step="SAR specialist initialized",
            status="complete",
        ),
        ExecutionStep(
            step="SAR / optical-SAR analysis",
            status="stub",
        ),
    ]

    answer = (
        "The query was successfully routed to the SAR analysis "
        "specialist. SAR interpretation and optical-SAR fusion will "
        "be connected in the dedicated SAR milestone."
    )

    confidence = 0.50

    return answer, confidence, trace