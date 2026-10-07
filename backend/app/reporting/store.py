"""Saves each analysis so a report can be generated for it later."""

import os
import re
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from backend.app.ingestion.store import UPLOAD_DIR
from backend.app.models.query import AnalyzeRequest, AnalyzeResponse

ANALYSIS_DIR = os.path.join(UPLOAD_DIR, "analyses")

_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class AnalysisRecord(BaseModel):
    analysis_id: str
    created_at: datetime
    image_id: str | None = None
    image_id_2: str | None = None
    response: AnalyzeResponse


def save_analysis(
    request: AnalyzeRequest,
    response: AnalyzeResponse,
    directory: str = ANALYSIS_DIR,
) -> AnalysisRecord:
    """Assigns an id to the response, stores it, and returns the record."""

    response.analysis_id = uuid.uuid4().hex

    record = AnalysisRecord(
        analysis_id=response.analysis_id,
        created_at=datetime.now(timezone.utc),
        image_id=request.image_id,
        image_id_2=request.image_id_2,
        response=response,
    )

    os.makedirs(directory, exist_ok=True)

    with open(os.path.join(directory, f"{record.analysis_id}.json"), "w") as handle:
        handle.write(record.model_dump_json(indent=2))

    return record


def load_analysis(
    analysis_id: str,
    directory: str = ANALYSIS_DIR,
) -> AnalysisRecord | None:
    # The id becomes part of a file path, so only accept ids we generated.
    if not _ID_PATTERN.match(analysis_id or ""):
        return None

    path = os.path.join(directory, f"{analysis_id}.json")

    if not os.path.exists(path):
        return None

    with open(path) as handle:
        return AnalysisRecord.model_validate_json(handle.read())
