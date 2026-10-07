from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from backend.app.ingestion.raster import inspect_raster, create_preview
from backend.app.controller.controller import analyze_query, default_info_loader
from backend.app.ingestion.info import check_pair
from backend.app.models.query import AnalyzeRequest, AnalyzeResponse
from backend.app.reporting.report import build_report_html
from backend.app.reporting.store import load_analysis, save_analysis


app = FastAPI(title="SatQuery AI")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "SatQuery AI API is running"
    }


@app.post("/inspect-raster")
def inspect_uploaded_raster(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No file provided"
        )

    filename = os.path.basename(file.filename)

    if not filename.lower().endswith((".tif", ".tiff")):
        raise HTTPException(
            status_code=400,
            detail="Only .tif and .tiff files are supported"
        )

    os.makedirs("uploads", exist_ok=True)

    file_path = os.path.join("uploads", filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        metadata = inspect_raster(file_path)

        preview_filename = os.path.splitext(filename)[0] + "_preview.png"
        preview_path = os.path.join("uploads", preview_filename)

        create_preview(file_path, preview_path)

        return {
            "filename": filename,
            "metadata": metadata,
            "preview": preview_filename
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read raster file: {str(e)}"
        )


@app.get("/preview/{filename}")
def get_preview(filename: str):
    filename = os.path.basename(filename)
    file_path = os.path.join("uploads", filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Preview not found"
        )

    return FileResponse(
        file_path,
        media_type="image/png"
    )


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
)
def analyze(request: AnalyzeRequest):
    try:
        response = analyze_query(request)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )

    try:
        # Stored so GET /report/{analysis_id} can build the report later.
        save_analysis(request, response)
    except OSError:
        # The analysis itself succeeded; it just has no downloadable report.
        response.analysis_id = None

    return response


def _read_upload_png(filename: str | None) -> bytes | None:
    if not filename:
        return None

    path = os.path.join("uploads", os.path.basename(filename))

    if not path.lower().endswith(".png") or not os.path.exists(path):
        return None

    with open(path, "rb") as handle:
        return handle.read()


@app.get("/report/{analysis_id}", response_class=HTMLResponse)
def download_report(analysis_id: str):
    """Self-contained HTML report for a previous /analyze call."""

    record = load_analysis(analysis_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Report not found")

    preview = None

    if record.image_id:
        stem = os.path.splitext(os.path.basename(record.image_id))[0]
        preview = _read_upload_png(f"{stem}_preview.png")

    html = build_report_html(
        record,
        overlay_png=_read_upload_png(record.response.overlay),
        preview_png=preview,
    )

    return HTMLResponse(
        content=html,
        headers={
            "Content-Disposition": (
                f'attachment; filename="satquery-report-{analysis_id}.html"'
            )
        },
    )


@app.get("/compatibility")
def compatibility(image_id: str, image_id_2: str):
    """Ingestion report for two uploaded images (modality, co-registration, time)."""

    info_1 = default_info_loader(image_id)
    info_2 = default_info_loader(image_id_2)

    if info_1 is None or info_2 is None:
        raise HTTPException(
            status_code=404,
            detail="One or both images were not found or could not be read",
        )

    return {
        "image_1": info_1,
        "image_2": info_2,
        "pair": check_pair(info_1, info_2),
    }
