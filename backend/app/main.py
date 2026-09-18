from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from backend.app.ingestion.raster import inspect_raster, create_preview
from backend.app.controller.controller import analyze_query
from backend.app.models.query import AnalyzeRequest, AnalyzeResponse


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
        return analyze_query(request)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )