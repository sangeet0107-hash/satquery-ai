from typing import Callable

from backend.app.controller.preflight import run_preflight
from backend.app.controller.registry import get_tool
from backend.app.controller.router import Router, RuleRouter
from backend.app.ingestion.info import RasterInfo, check_pair
from backend.app.models.query import (
    AnalyzeRequest,
    AnalyzeResponse,
    ExecutionStep,
    TaskType,
)

InfoLoader = Callable[[str | None], RasterInfo | None]


def default_info_loader(image_id: str | None) -> RasterInfo | None:
    """Parse an uploaded image; None if it is missing or unreadable."""

    from backend.app.ingestion.store import resolve_upload_path

    path = resolve_upload_path(image_id)

    if path is None:
        return None

    try:
        from backend.app.ingestion.raster import read_raster_info

        return read_raster_info(path, image_id=image_id)
    except Exception:
        return None


def _describe(info: RasterInfo, label: str) -> str:
    return (
        f"{label}: {info.modality.value} "
        f"({info.modality_confidence} confidence), {info.bands} band(s), "
        f"{info.width}x{info.height} px"
    )


def analyze_query(
    request: AnalyzeRequest,
    info_loader: InfoLoader | None = None,
    router: Router | None = None,
) -> AnalyzeResponse:
    info_loader = info_loader or default_info_loader
    router = router or RuleRouter()

    trace: list[ExecutionStep] = [
        ExecutionStep(
            step="Query received by controller",
            status="complete",
        )
    ]

    # 5.1 Ingestion: deterministic parsing of whatever was uploaded.
    info = info_loader(request.image_id)
    info_2 = info_loader(request.image_id_2)

    for label, parsed in (("Image 1", info), ("Image 2", info_2)):
        if parsed is not None:
            trace.append(
                ExecutionStep(
                    step=f"Ingestion - {_describe(parsed, label)}",
                    status="complete",
                    tool="raster-ingestion",
                    params={"reason": parsed.modality_reason},
                )
            )

    pair = check_pair(info, info_2) if info and info_2 else None

    if pair is not None:
        trace.append(
            ExecutionStep(
                step=(
                    f"Pair check - {pair.pair_type.value}, "
                    f"co-registered={pair.co_registered}, "
                    f"bitemporal={pair.bitemporal}"
                ),
                status="complete",
                tool="raster-ingestion",
                params={"issues": pair.issues},
            )
        )

    # 5.2 Routing.
    decision = router.route(request.query, [i for i in (info, info_2) if i])
    task = decision.task

    trace.append(
        ExecutionStep(
            step=f"Query classified as {task.value}",
            status="complete",
            tool=decision.router,
            params={"rationale": decision.rationale},
        )
    )

    tool = get_tool(task)
    params = tool.build_params()

    trace.append(
        ExecutionStep(
            step=f"Selected tool '{tool.name}' for {task.value}",
            status="complete",
            tool=tool.name,
            params=params.model_dump(),
        )
    )

    # Preflight: stop early, with an explanation, if the imagery cannot
    # support the requested task.
    check = run_preflight(
        task=task,
        image_id=request.image_id,
        image_id_2=request.image_id_2,
        info=info,
        info_2=info_2,
        pair=pair,
    )

    for warning in check.warnings:
        trace.append(ExecutionStep(step=f"Warning - {warning}", status="warning"))

    if not check.ok:
        for blocker in check.blockers:
            trace.append(
                ExecutionStep(step=f"Blocked - {blocker}", status="blocked")
            )

        return AnalyzeResponse(
            query=request.query,
            task=task,
            answer=(
                f"I can't run {task.value} on the current imagery: "
                + "; ".join(check.blockers)
                + "."
            ),
            confidence=0.10,
            execution_trace=trace,
        )

    answer, confidence, specialist_trace = tool.runner(
        request.query,
        request.image_id,
        request.image_id_2,
        params,
    )

    trace.append(
        ExecutionStep(
            step=f"Routed request to {task.value} specialist",
            status="complete",
            tool=tool.name,
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
