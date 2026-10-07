# SatQuery AI — Project Roadmap, Workflow & Progress Tracker

> **Purpose:** This document is the implementation roadmap for SatQuery AI. It maps the current codebase and Git milestones to the features described in the project proposal, so the team can track what is implemented, what is partially implemented, and what remains.
>
> **Source of truth:** SatQueryAI proposal PDF supplied with the project. This roadmap preserves the proposal's major architecture and feature requirements while turning them into implementation tasks.
>
> **Last updated:** 2026-10-07, after the SAR specialist merge (`65b830f`).
>
> **How to read the checkboxes:** `[x]` means implemented and covered by tests that have been run. An unchecked item with a note in italics is partly done, or written but not yet verified; the note says which.

---

## 1. Project Goal

SatQuery AI is intended to be a unified conversational interface for remote-sensing imagery. A user should be able to upload satellite imagery, ask a natural-language question, and have the system automatically determine the required analysis capability, invoke the appropriate specialist model/tool, and return an evidence-grounded answer with confidence and an auditable execution trace.

The proposal explicitly calls for support for:

- single optical/multispectral imagery
- single SAR imagery
- co-registered optical-SAR pairs
- bi-temporal image pairs
- GeoTIFF/TIFF ingestion
- natural-language query routing
- VQA / captioning
- visual grounding
- multitemporal change understanding
- optical-SAR fusion
- visual evidence such as highlights, bounding boxes, or masks
- confidence estimates
- auditable execution traces
- downloadable reports
- optional adaptation toward Indian sensor characteristics such as Cartosat-2S and RISAT
- quantitative confidence, uncertainty, temporal and model-risk analysis
- object-level dynamics and behavioral signatures
- retrieval/memory
- experiment tracking
- containerization
- automated tests / CI

---

## 2. Current Architecture

```text
                         ┌──────────────────────┐
                         │     React Frontend   │
                         │  Upload + Query + UI │
                         └──────────┬───────────┘
                                    │ HTTP
                                    ▼
                         ┌──────────────────────┐
                         │     FastAPI API      │
                         │       main.py        │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
        ┌───────────────────┐              ┌─────────────────────┐
        │ Ingestion Layer  │              │ Agentic Controller  │
        │ Rasterio/GDAL    │              │ Query classification │
        └─────────┬─────────┘              └──────────┬──────────┘
                  │                                   │
                  │                                   ▼
                  │                    ┌────────────────────────┐
                  │                    │ Specialist Tool Layer  │
                  │                    │                        │
                  │                    │ VQA                    │
                  │                    │ Grounding              │
                  │                    │ Change                  │
                  │                    │ Optical-SAR             │
                  │                    └───────────┬────────────┘
                  │                                │
                  └────────────────┬───────────────┘
                                   ▼
                         ┌──────────────────────┐
                         │ Output Integration   │
                         │ Answer               │
                         │ Evidence             │
                         │ Confidence           │
                         │ Execution trace      │
                         └──────────┬───────────┘
                                    ▼
                         ┌──────────────────────┐
                         │ Frontend Results UI  │
                         └──────────────────────┘
```

---

# 3. Git / Milestone Progress

## Milestone 0 — Repository Setup
**Status: COMPLETE**

Completed:

- GitHub repository/fork configured.
- `origin` points to the working fork.
- `upstream` points to the original repository.
- Main development branch is `main`.
- Local repository synchronized with `origin/main`.

### Team rule

Every meaningful feature should produce a commit.

Recommended commit format:

```text
feat: add <feature>
fix: <bug>
test: add <tests>
docs: update <documentation>
refactor: <change>
chore: <maintenance>
```

---

## Milestone 1 — Raster Ingestion Foundation
**Status: COMPLETE**

Implemented:

- FastAPI backend.
- `GET /`
- `POST /inspect-raster`
- GeoTIFF/TIFF validation.
- Rasterio-based metadata extraction.
- Preview PNG generation.
- `GET /preview/{filename}`
- Upload storage under `uploads/`.
- Synthetic GeoTIFF test dataset.

Main files:

```text
backend/app/main.py
backend/app/ingestion/raster.py
backend/app/ingestion/info.py      (modality, dates, pair checks)
backend/app/ingestion/access.py    (file access used by specialists)
backend/app/ingestion/store.py     (upload lookup)
requirements.txt
```

### Proposal mapping

Maps to:

- Ingestion & Compatibility Layer
- GeoTIFF/TIFF support
- deterministic raster parsing
- metadata extraction
- preview generation

### Remaining ingestion work

- [x] Detect optical vs multispectral vs SAR. *(heuristic: metadata and file-name hints first, then band count; it reports its own confidence and reason)*
- [ ] Detect/record band semantics where metadata allows. *(not done: bands 1-3 are assumed to be R, G, B, and fusion assumes band 4 is near-infrared)*
- [x] Validate paired-image compatibility.
- [x] Check spatial dimensions.
- [x] Check CRS compatibility.
- [x] Check transform/georeferencing compatibility. *(pixel size and extent overlap)*
- [x] Check co-registration. *(from metadata only: same CRS, grid and extent; actual image alignment is not measured)*
- [x] Detect temporal metadata. *(acquisition tags first, then a date in the file name)*
- [ ] Support multiple uploaded images cleanly. *(two images work end to end; the UI always sends the first two uploads)*
- [ ] Return a stable image identifier. *(still the raw filename, so two uploads with the same name overwrite each other)*
- [ ] Store ingestion metadata in a persistent database later.

---

## Milestone 2 — Mission-Control Frontend
**Status: COMPLETE**

Implemented:

- Header/system status.
- Data-source sidebar.
- Upload interaction.
- Image context/metadata area.
- Viewer.
- Image / Map / Split modes.
- Query box.
- Query suggestions.
- Analysis tab.
- Evidence tab.
- Execution Trace tab.
- Capability list.
- Responsive/polished UI styling.

Main files:

```text
frontend/src/App.jsx
frontend/src/App.css
frontend/src/index.css
frontend/package.json
```

### Remaining frontend work

- [ ] Replace placeholder raster viewer with real rendered imagery everywhere.
- [ ] Add real map rendering with Leaflet or Mapbox GL.
- [ ] Render bounding boxes. *(drawn by the backend into one evidence image shown in the Evidence tab; not interactive and not on the main viewer)*
- [ ] Render masks. *(drawn by the backend into one evidence image shown in the Evidence tab; not interactive and not on the main viewer)*
- [ ] Render change maps. *(drawn by the backend into one evidence image shown in the Evidence tab; not interactive and not on the main viewer)*
- [ ] Render optical-SAR overlays. *(drawn by the backend into one evidence image shown in the Evidence tab; not interactive and not on the main viewer)*
- [ ] Support selecting multiple datasets.
- [ ] Add report download. *(link added in the Evidence tab; not yet confirmed in a browser)*
- [ ] Add richer evidence panels. *(basic panel added: overlay image plus a list of evidence items with boxes and scores)*
- [ ] Add query history / retrieval UI if needed.

---

## Milestone 3 — Frontend ↔ Backend Analysis Integration
**Status: COMPLETE**

Implemented:

- Frontend calls `POST /analyze`.
- Query sent to backend.
- `image_id` and optional `image_id_2` are supported.
- Analysis response stored in frontend state.
- Answer displayed.
- Confidence displayed.
- Execution trace displayed.
- Error state handled.
- Real execution trace verified manually.

Main backend files:

```text
backend/app/main.py
backend/app/controller/controller.py
backend/app/controller/classifier.py
backend/app/models/query.py
```

---

## Milestone 4 — Rule-Based Controller
**Status: COMPLETE AS MVP ROUTER**

Current routing priority:

```text
SAR
  ↓
CHANGE
  ↓
GROUNDING
  ↓
VQA
  ↓
UNKNOWN
```

Current classifier uses keyword/rule matching.

Main file:

```text
backend/app/controller/classifier.py   (keyword rules)
backend/app/controller/router.py       (Router interface; RuleRouter wraps the classifier)
backend/app/controller/registry.py     (tool registry)
backend/app/controller/preflight.py    (checks before any tool runs)
```

The keyword classifier is kept as `RuleRouter`, the deterministic fallback asked for below. An LLM router can implement the same `Router` interface without changing the controller.

### Proposal target

The proposal describes an agentic controller where an LLM reads the query plus ingestion information and selects tools from a predefined registry.

### Remaining controller work

- [x] Add ingestion metadata to routing context. *(passed to the router and used by the preflight checks; the rule router itself does not use it yet)*
- [x] Create formal tool registry.
- [x] Define permitted parameters for each specialist. *(strict Pydantic models; unknown or out-of-range values are rejected)*
- [ ] Preserve structured routing state. *(each decision is recorded in the trace as task, router and rationale; there is no multi-step state)*
- [ ] Add LangGraph/LangChain orchestration if justified.
- [ ] Add multi-tool routing for queries requiring more than one capability.
- [x] Add routing tests.
- [ ] Backtest routing against labelled queries.
- [ ] Measure routing accuracy.
- [ ] Measure false-positive task selection.
- [ ] Measure calibration error later.

**Important:** Do not replace the working classifier blindly. First preserve it as a deterministic fallback.

---

# 4. Specialist Model Roadmap

## 4.1 VQA
**Status: FUNCTIONAL FIRST AI MILESTONE**

Implemented:

- VQA specialist interface.
- Uploaded-image resolution.
- GeoTIFF loading as an RGB composite of bands 1-3 (single-band rasters as greyscale).
- Numeric normalization.
- RGB conversion.
- BLIP VQA model loading.
- CPU inference.
- Answer generation.
- Execution trace.
- Placeholder system confidence (fixed 0.70).
- Model name and parameters recorded in the execution trace.

Main file:

```text
backend/app/specialists/vqa.py
```

Current model:

```text
Salesforce/blip-vqa-base
```

### Important limitation

BLIP is a general-image VQA model, not a satellite-specific model. It establishes the end-to-end real inference pipeline.

### Next VQA tasks

- [ ] Test on real optical satellite imagery.
- [ ] Test on multispectral imagery.
- [ ] Evaluate answers against a small labelled question set.
- [ ] Add satellite-specific preprocessing.
- [ ] Investigate GeoChat or another remote-sensing VLM.
- [ ] Compare model outputs.
- [ ] Replace placeholder confidence with calibrated confidence.
- [ ] Return structured evidence where possible.
- [ ] Add captioning capability if included in the specialist registry.

---

## 4.2 Visual Grounding
**Status: IMPLEMENTED, MODEL NOT YET RUN**

Everything around the model is tested with a fake detector. The real model has never been executed, so treat this specialist as unverified until one real grounding query has been run.

Current files:

```text
backend/app/specialists/grounding.py   (OWL-ViT wrapper, answer, evidence)
backend/app/analysis/grounding.py      (target extraction, tiling, box merging)
```

Required:

- [x] Load actual image.
- [x] Accept referring expressions such as:
      - "Where are the buildings?"
      - "Locate the ships."
      - "Find the road."
      *(done: the target object is pulled out of the question by rules)*
- [ ] Run a grounding/localization model. *(wired to OWL-ViT `google/owlvit-base-patch32` through the transformers zero-shot detection pipeline, on CPU; never executed)*
- [x] Return bounding boxes and/or masks. *(boxes only)*
- [x] Return textual interpretation.
- [x] Return model score. *(raw detector score, uncalibrated)*
- [x] Produce visual overlay.
- [x] Persist evidence coordinates. *(stored with each analysis under `uploads/analyses/`)*
- [ ] Display evidence in frontend. *(Evidence tab added; not yet confirmed in a browser)*
- [ ] Add evaluation metrics such as IoU where labelled data exists.

---

## 4.3 Multitemporal Change Understanding
**Status: FUNCTIONAL BASELINE (pixel-level, no learned model)**

It reports where the imagery changed and by how much. It cannot say what kind of change it is, and the answer text says so. Only two images on the same pixel grid are supported.

Current files:

```text
backend/app/specialists/change.py   (answer, evidence, area)
backend/app/analysis/change.py      (change vector analysis)
backend/app/analysis/masks.py       (threshold and mask cleanup, shared with SAR)
```

Required:

- [x] Accept two images.
- [x] Validate that both are compatible. *(pairs with different pixel dimensions are refused with an explanation)*
- [x] Check spatial alignment / co-registration. *(metadata check, plus tolerance for 1 px of misalignment by default, adjustable to 3)*
- [x] Identify acquisition dates where available.
- [x] Compute baseline change representation. *(change vector analysis on robustly standardised bands)*
- [ ] Connect a change-understanding model. *(not done)*
- [x] Generate change mask/map.
- [ ] Explain detected changes in natural language. *(partly: location, size and brighter/darker, but not the type of change)*
- [x] Quantify changed area. *(percentage of the scene, and ground area when georeferenced)*
- [ ] Report uncertainty interval.
- [ ] Add temporal change-point detection.
- [ ] Add rolling z-score anomaly detection.
- [ ] Add EWMA smoothing where appropriate.
- [ ] Support queries such as:
      - "What changed?"
      - "Where was construction detected?"
      - "How much built-up area increased?"
      - "When did the change begin?" for image stacks.

---

## 4.4 Optical-SAR Fusion
**Status: FUNCTIONAL BASELINE (classical, no learned model)**

Tested on simulated speckle only. "Water-like" means low backscatter; tarmac, smooth bare ground and radar shadow look the same, and every answer that reports such a surface says so.

Current files:

```text
backend/app/specialists/sar.py   (image selection, answer, evidence)
backend/app/analysis/sar.py      (speckle filter, water-like mask, bright targets, fusion)
```

Required:

- [x] Accept optical image + SAR image. *(in either order; a single SAR image also works)*
- [x] Validate pair.
- [x] Validate co-registration. *(metadata check; fusion is skipped with a warning when the grids differ)*
- [x] Identify modalities.
- [x] Normalize optical and SAR inputs appropriately. *(SAR: decibel/linear detection and Lee speckle filter; optical: band 4 as near-infrared when present, else mean brightness)*
- [ ] Connect a joint optical-SAR model. *(not done: fusion is decision-level agreement between a SAR low-backscatter mask and an optical dark-surface mask)*
- [x] Return textual answer.
- [x] Return evidence.
- [x] Return confidence. *(uncalibrated heuristic)*
- [x] Visualize paired evidence. *(colour-coded overlay: dark in both, SAR only, optical only)*
- [ ] Test with Sentinel-1/Sentinel-2 where available. *(not done: simulated data only)*
- [ ] Investigate proposal examples such as EarthMind / Earth-OneVision.

---

## 4.5 Unknown / Unsupported Task
**Status: FUNCTIONAL FALLBACK**

Current file:

```text
backend/app/specialists/unknown.py
```

Keep this.

For recognised tasks, the preflight checks now explain what is missing (for example, a second image for change detection) before any tool runs.

Required improvements:

- [ ] Explain what information/task is missing.
- [ ] Suggest supported query types.
- [ ] Avoid pretending unsupported analysis was performed.

---

# 5. Evidence-Grounded Output Layer

**Status: IMPLEMENTED IN THE BACKEND (frontend display not yet confirmed)**

The proposal requires answers that are not only free text, but are accompanied by evidence such as visual highlights, bounding boxes, or masks.

Required output structure should eventually resemble:

```json
{
  "query": "...",
  "task": "GROUNDING",
  "answer": "...",
  "confidence": 0.82,
  "evidence": {
    "type": "bounding_boxes",
    "image_id": "...",
    "boxes": [
      {
        "x1": 100,
        "y1": 120,
        "x2": 180,
        "y2": 200,
        "label": "building",
        "score": 0.91
      }
    ]
  },
  "execution_trace": []
}
```

The implemented schema is flatter than the sketch above: `evidence` is a list of items, each with `kind` (`bbox` or `mask`), `label`, `bbox` as `[x_min, y_min, x_max, y_max]`, `mask_ref` and `score`. The response also carries `overlay` (the rendered evidence image) and `analysis_id`.

Tasks:

- [x] Extend Pydantic response models.
- [x] Define evidence schema.
- [x] Support bounding boxes.
- [x] Support masks.
- [x] Support highlighted regions. *(as tinted masks in the overlay image)*
- [x] Support change maps. *(change mask saved as a PNG)*
- [ ] Add geospatial coordinates when possible. *(not done: evidence is in pixel coordinates only)*
- [ ] Render evidence in React. *(Evidence tab shows the backend-rendered overlay and the item list; not yet confirmed in a browser)*
- [x] Preserve source-image coordinate system. *(boxes are mapped back to source pixels when the analysis ran at reduced resolution)*
- [ ] Make evidence downloadable. *(mask and overlay PNGs are served by `/preview/{filename}` and the overlay is embedded in the report; there is no download button)*

---

# 6. Confidence & Uncertainty Layer

**Status: PARTIAL / PLACEHOLDER**

The current VQA confidence is a temporary system value and should NOT be presented as calibrated model probability.

The same now applies to every specialist. All four return a confidence, and none is calibrated: VQA is a fixed 0.70, grounding is the mean raw detector score, and change and SAR use contrast-based heuristics. The execution trace and the report label them as uncalibrated.

Proposal requirements:

- Platt scaling or isotonic regression.
- Confidence based on empirical specialist accuracy.
- Change magnitudes represented with confidence intervals.
- Interval-based reporting for uncertain outputs.
- Sensitivity analysis.

Tasks:

- [ ] Collect labelled validation queries.
- [ ] Store raw specialist scores.
- [ ] Build calibration dataset.
- [ ] Implement Platt scaling.
- [ ] Compare with isotonic regression.
- [ ] Select calibration method using validation evidence.
- [ ] Store calibration parameters/version.
- [ ] Produce calibrated confidence.
- [ ] Add confidence intervals for quantitative change estimates.
- [ ] Add sensitivity analysis for:
      - cloud cover
      - SAR speckle noise
      - preprocessing perturbations
- [ ] Display uncertainty in UI.

---

# 7. Quantitative Remote-Sensing Analysis

**Status: PARTIAL (area measurement only)**

The proposal calls for quantitative techniques beyond simple text answers.

## Required components

### Change-point detection

Implement one or both:

- [ ] CUSUM
- [ ] Bayesian Online Change Point Detection

Purpose:

- identify when meaningful change began in a time series/image stack.

### Rolling anomaly scoring

- [ ] Rolling z-score.
- [ ] Establish historical baseline per region/object.
- [ ] Flag significant spectral or SAR-backscatter deviations.

### EWMA

- [ ] Implement EWMA smoothing.
- [ ] Use for noisy multitemporal signals such as NDVI drift.

### Area/change measurements

- [x] Calculate changed area.
- [x] Convert pixel counts to physical area using georeferencing.
- [ ] Report percentage increase/decrease. *(the share of the scene that changed is reported; increase or decrease of a specific land cover is not)*
- [ ] Attach uncertainty interval.

---

# 8. Ensemble & Model-Risk Layer

**Status: NOT IMPLEMENTED**

Proposal requirements:

- [ ] Weighted voting across overlapping specialist outputs.
- [ ] Derive weights from historical calibrated accuracy.
- [ ] Build held-out labelled query set.
- [ ] Backtest controller.
- [ ] Report routing accuracy.
- [ ] Report false-positive task-selection rate.
- [ ] Report calibration error.
- [ ] Produce validation table.

Suggested architecture:

```text
Specialist A ─┐
Specialist B ─┼──> calibrated scores ──> weighted ensemble ──> result
Specialist C ─┘
```

Do not add ensemble complexity until at least two useful specialist models produce comparable structured outputs.

---

# 9. Object-Level Dynamics & Behavioral Modeling

**Status: NOT IMPLEMENTED**

This is an advanced proposal feature and should be implemented after the core detection/change pipeline works.

## 9.1 Static / land-cover object dynamics

Object classes mentioned in the proposal include:

- fields
- water bodies
- built-up areas
- forest patches

Tasks:

- [ ] Maintain object identity across dates.
- [ ] Assign object state.
- [ ] Build historical state sequence.
- [ ] Define state-transition profiles.
- [ ] Train/fit HMM per object class.
- [ ] Predict next-state probability.
- [ ] Return current state + predicted next state.

Example:

```text
field:
fallow → sown → mature → harvested
```

or:

```text
water body:
full → receding → dry
```

## 9.2 Agentive object behavior

For genuinely moving objects such as:

- vehicles
- vessels
- human-activity clusters

Tasks:

- [ ] Track objects across frames/dates.
- [ ] Estimate trajectory.
- [ ] Implement Kalman filtering where appropriate.
- [ ] Classify behavior:
      - stationary
      - transiting
      - loitering
      - anomalous
- [ ] Avoid claiming "intent" beyond what the evidence supports.

## 9.3 Scene-level behavioral signature

Tasks:

- [ ] Aggregate object states.
- [ ] Produce structured scene signature.
- [ ] Store signature.
- [ ] Compare current signature against historical baseline.
- [ ] Connect with anomaly detection.
- [ ] Surface scene-level changes through natural-language queries.

---

# 10. Retrieval & Memory

**Status: NOT IMPLEMENTED**

Proposal technology stack specifies a vector database and lightweight RAG.

Possible open-source options mentioned:

- FAISS
- Qdrant
- Milvus

Required:

- [ ] Define trace/evidence document schema.
- [ ] Store past query-answer-evidence traces.
- [ ] Generate embeddings.
- [ ] Store embeddings.
- [ ] Similarity search.
- [ ] Retrieve similar historical analyses.
- [ ] Add lightweight RAG over annotation/documentation data.
- [ ] Investigate BigEarthNet captions/annotations as a retrieval source.
- [ ] Return retrieved context to specialist/controller only where useful.
- [ ] Record retrieval steps in execution trace.

For the one-month MVP, FAISS is the simplest starting point unless persistent multi-user storage becomes necessary.

---

# 11. Geospatial Database

**Status: NOT IMPLEMENTED**

Proposal specifies PostgreSQL + PostGIS for:

- georeferenced metadata
- bounding boxes
- masks
- spatial querying

Tasks:

- [ ] Define database schema.
- [ ] Store raster metadata.
- [ ] Store image footprints.
- [ ] Store acquisition timestamps.
- [ ] Store bounding boxes.
- [ ] Store masks/geometries.
- [ ] Store evidence references.
- [ ] Add spatial queries.
- [ ] Connect FastAPI.
- [ ] Add migrations.
- [ ] Add database tests.

For the prototype, SQLite or filesystem storage may be used temporarily, but PostGIS is the target architecture described by the proposal.

---

# 12. Geospatial Processing

**Status: PARTIAL**

Current:

- Rasterio.
- GeoTIFF parsing.
- Band reading.
- Metadata.
- Preview generation.

Proposal additionally mentions GDAL / Rasterio and optional QGIS export.

Tasks:

- [ ] Band extraction.
- [ ] Multiband visualization.
- [ ] CRS handling. *(the CRS is read and compared; nothing is reprojected)*
- [ ] Pixel-to-coordinate conversion.
- [x] Co-registration checks. *(from metadata)*
- [ ] Raster alignment.
- [ ] Resampling. *(only downsampling of large rasters before analysis)*
- [ ] Spatial footprint calculation.
- [ ] Evidence coordinate conversion.
- [ ] Optional QGIS-compatible overlay export.

---

# 13. Map & Visualization

**Status: PARTIAL**

Current:

- Viewer UI.
- Image / Map / Split controls.
- Preview support.

Proposal target:

- React.
- Leaflet or Mapbox GL.
- Overlay rendering.

Tasks:

- [ ] Integrate Leaflet or Mapbox GL.
- [ ] Display georeferenced raster.
- [ ] Display image footprint.
- [ ] Zoom/pan.
- [ ] Bounding-box overlays.
- [ ] Mask overlays.
- [ ] Change-map overlay.
- [ ] Optical-SAR comparison.
- [ ] Coordinate readout.
- [ ] Layer toggles.
- [ ] Legend.
- [ ] Export overlays.

---

# 14. Downloadable Report

**Status: IMPLEMENTED AS HTML (PDF not done)**

Proposal requires a downloadable report containing:

- answer
- supporting visuals
- confidence information
- full execution trace
- selected task
- model/tool used
- parameters applied

Tasks:

- [x] Define report schema. *(`AnalysisRecord`: id, time, image names and the full response)*
- [ ] Generate PDF. *(not done: the report is one self-contained HTML file, which prints to PDF from a browser)*
- [ ] Include source metadata. *(image names only)*
- [x] Include query.
- [x] Include answer.
- [x] Include evidence image(s).
- [x] Include confidence. *(labelled as uncalibrated)*
- [ ] Include uncertainty.
- [x] Include execution trace.
- [x] Include model/tool names.
- [x] Include parameters.
- [x] Add download endpoint. *(`GET /report/{analysis_id}`)*
- [ ] Add frontend download button. *(link added in the Evidence tab; not yet confirmed in a browser)*

---

# 15. Domain Adaptation

**Status: NOT IMPLEMENTED**

Proposal says this is optional / "where time permits."

Dataset mentioned:

```text
BigEarthNet.txt
```

The proposal describes it as containing co-registered Sentinel-1 SAR and Sentinel-2 multispectral imagery with captioning, VQA, and referring-expression annotations.

Tasks:

- [ ] Acquire permitted dataset.
- [ ] Inspect annotation format.
- [ ] Build dataset loader.
- [ ] Prepare VQA/captioning examples.
- [ ] Prepare referring-expression examples.
- [ ] Establish baseline.
- [ ] Fine-tune selected specialist model.
- [ ] Track runs.
- [ ] Evaluate before/after.
- [ ] Record limitations.

### Indian sensor adaptation

Target characteristics mentioned:

- Cartosat-2S optical
- RISAT SAR

Tasks:

- [ ] Obtain suitable permitted sample data.
- [ ] Compare resolution/sensor characteristics against training data.
- [ ] Perform preprocessing adaptation.
- [ ] Fine-tune where feasible.
- [ ] Evaluate separately.
- [ ] Explicitly document remaining resolution/sensor-frequency gaps.

Do NOT claim that Sentinel-only fine-tuning solves Cartosat/RISAT adaptation.

---

# 16. MLOps & Experiment Tracking

**Status: NOT IMPLEMENTED**

Proposal mentions:

- MLflow
- Weights & Biases
- model checkpoint versioning

Tasks:

- [ ] Define experiment naming.
- [ ] Record model name/version.
- [ ] Record dataset version.
- [ ] Record preprocessing version.
- [ ] Record metrics.
- [ ] Record calibration results.
- [ ] Track fine-tuning runs.
- [ ] Store model checkpoints.
- [ ] Connect experiment IDs to execution trace.

For the prototype, MLflow is a practical open-source choice.

---

# 17. Specialist Containerization

**Status: NOT IMPLEMENTED**

Proposal specifies Docker / Docker Compose.

Target:

```text
docker-compose
├── api
├── vqa
├── grounding
├── change
├── sar
├── postgres
├── vector-db
└── optional frontend
```

Tasks:

- [ ] Dockerfile for backend.
- [ ] Dockerfile for specialist services where needed.
- [ ] Docker Compose.
- [ ] Health endpoints.
- [ ] Environment variables.
- [ ] Model cache volumes.
- [ ] Resource limits.
- [ ] Service-to-service communication.
- [ ] Reproducible startup.

Do this after the local Python pipeline is stable.

---

# 18. CI/CD

**Status: NOT IMPLEMENTED**

Proposal specifies GitHub Actions.

Required minimum CI:

- [ ] Install backend dependencies.
- [ ] Run Python syntax checks.
- [ ] Run ingestion tests.
- [ ] Run classifier tests.
- [ ] Run API tests.
- [ ] Build frontend.
- [ ] Run frontend lint/test if configured.

The tests below already exist and can be run by CI as they are; there is no workflow file yet.

Recommended test groups:

```text
tests/
├── test_ingestion.py
├── test_classifier.py
├── test_api.py
├── test_vqa.py
├── test_change.py
├── test_grounding.py
└── test_sar.py
```

Actual layout as of 2026-10-07:

```text
backend/tests/
├── test_ingestion.py           (real GeoTIFF reads)
├── test_ingestion_info.py      (modality, dates, pair checks)
├── test_classifier.py
├── test_controller.py
├── test_preflight_registry.py
├── test_api.py                 (upload → analyze → report)
├── test_change_analysis.py
├── test_grounding_analysis.py
├── test_overlay_report.py
├── test_specialists.py         (change and grounding, in-memory)
├── test_sar_analysis.py
├── test_sar_specialist.py
└── helpers.py
```

There is no VQA test: it would need the BLIP model.

---

# 19. Kubernetes

**Status: FUTURE SCOPE**

The proposal mentions Kubernetes as future deployment infrastructure.

Do NOT prioritize this for the one-month prototype.

Only implement after:

- core specialists work
- Docker Compose works
- API contracts are stable
- evaluation is complete

---

# 20. Security & Reliability Tasks

**Status: PARTIAL**

Already:

- filename basename handling
- file extension validation
- API validation through Pydantic

Tasks:

- [ ] File-size limits.
- [ ] Raster dimension limits. *(large rasters are analysed at reduced resolution, but uploads are not rejected by size)*
- [ ] Safe upload naming.
- [x] Avoid arbitrary filesystem paths. *(upload names are reduced to their base name; report ids must match a fixed pattern)*
- [x] Validate all model parameters.
- [x] Restrict tool parameters.
- [x] Prevent unsupported tool execution. *(tools run only through the registry)*
- [ ] Error handling around malformed rasters.
- [ ] Model timeout handling.
- [ ] Memory/resource protection.
- [ ] Avoid exposing internal filesystem paths in API responses.

---

# 21. Testing Strategy

## Unit tests

- [x] Raster metadata extraction.
- [x] Preview creation.
- [ ] Invalid file rejection.
- [x] Query classifier.
- [ ] Image resolution.
- [x] VQA preprocessing. *(the shared raster-to-RGB loader)*
- [ ] Evidence schema validation.

## Integration tests

- [x] Upload → inspect.
- [ ] Upload → preview.
- [ ] Upload → analyze → VQA.
- [x] Two uploads → change.
- [ ] Optical + SAR → fusion. *(a single SAR upload → water mapping is covered through the API; the paired case is tested with in-memory rasters only)*
- [ ] Grounding → overlay. *(in-memory rasters and a fake detector only)*

## Model evaluation

Create a small labelled benchmark with:

```text
query
image(s)
expected task
expected answer/evidence
```

Measure:

- VQA answer accuracy where appropriate.
- Grounding IoU.
- Change detection metrics.
- SAR/fusion task accuracy.
- Routing accuracy.
- False-positive routing rate.
- Confidence calibration error.

---

# 22. Recommended One-Month Implementation Order

## Week 1 — Foundation + VQA

### Done

- [x] Repository setup.
- [x] FastAPI.
- [x] GeoTIFF ingestion.
- [x] Metadata.
- [x] Preview.
- [x] React interface.
- [x] `/analyze`.
- [x] Rule-based routing.
- [x] VQA specialist.
- [x] BLIP CPU inference.

### Remaining

- [ ] Better image registry.
- [ ] Real multi-image upload.
- [x] Ingestion modality detection.
- [ ] VQA evaluation set.
- [ ] VQA evidence support.

---

## Week 2 — Grounding + Change

### Grounding

- [ ] Actual grounding model. *(OWL-ViT wired in; never executed)*
- [x] Bounding boxes.
- [x] Overlay rendering.
- [x] Grounding API result schema.

### Change

- [x] Two-image ingestion.
- [x] Co-registration validation.
- [x] Change model/baseline. *(baseline)*
- [x] Change mask.
- [ ] Change explanation. *(location, size and direction only)*
- [x] Area calculation.

---

## Week 3 — SAR + Evidence + Confidence

### Optical-SAR

- [x] Pair validation.
- [x] Optical preprocessing. *(minimal: near-infrared band or mean brightness)*
- [x] SAR preprocessing.
- [x] Fusion model/baseline. *(baseline)*
- [x] Evidence output.

### Evidence

- [x] Unified evidence schema.
- [ ] Frontend overlays. *(backend-rendered image in the Evidence tab; not yet confirmed in a browser)*
- [x] Coordinates. *(pixel coordinates)*

### Confidence

- [ ] Collect validation results.
- [ ] Calibrate scores.
- [ ] Display calibrated confidence.
- [ ] Add uncertainty intervals.

---

## Week 4 — Integration + Evaluation + Demo

- [x] Controller/tool registry.
- [ ] Optional LangGraph integration.
- [ ] Retrieval/FAISS prototype.
- [x] Report generation. *(HTML)*
- [x] Test suite.
- [ ] GitHub Actions.
- [ ] MLflow tracking.
- [ ] Docker Compose if time permits.
- [ ] Object dynamics prototype if core system is stable.
- [ ] Demo dataset.
- [ ] End-to-end evaluation.
- [ ] Final UI polish.
- [ ] Final documentation.
- [ ] Demo rehearsal.

---

# 23. Priority Classification

## P0 — Must work for the core demo

- [x] GeoTIFF ingestion
- [x] Metadata
- [x] Preview
- [x] Natural-language query
- [x] Routing
- [x] Real VQA
- [ ] Grounding *(implemented; model not yet run)*
- [x] Change understanding *(pixel-level baseline)*
- [x] Optical-SAR pair analysis *(classical baseline)*
- [x] Evidence overlays
- [ ] Confidence *(returned everywhere, but uncalibrated)*
- [x] Execution trace
- [ ] Multiple image support *(two images work; no stable ids)*

## P1 — Strongly recommended

- [ ] LLM/agentic controller
- [x] Formal tool registry
- [x] Downloadable report *(HTML)*
- [ ] Real map viewer
- [x] Co-registration checks *(from metadata)*
- [ ] Calibrated confidence
- [ ] Basic evaluation benchmark
- [ ] GitHub Actions

## P2 — Advanced proposal additions

- [ ] FAISS/Qdrant/Milvus retrieval
- [ ] RAG
- [ ] PostGIS
- [ ] MLflow/W&B
- [ ] Docker Compose
- [ ] quantitative uncertainty
- [ ] time-series change-point detection
- [ ] anomaly scoring
- [ ] EWMA
- [ ] ensemble/model-risk layer

## P3 — Advanced / stretch

- [ ] HMM object state transitions
- [ ] Kalman trajectory modeling
- [ ] agentive behavior classification
- [ ] scene-level behavioral signatures
- [ ] Indian sensor adaptation
- [ ] Kubernetes

---

# 24. Current File-to-Feature Map

```text
backend/app/main.py
    API endpoints
    CORS
    upload              POST /inspect-raster
    preview             GET  /preview/{filename}   (also serves evidence images)
    analyze             POST /analyze
    pair report         GET  /compatibility
    report download     GET  /report/{analysis_id}

backend/app/ingestion/raster.py
    GeoTIFF inspection, metadata, preview
    raster → RGB image, raster → array, pixel ground area

backend/app/ingestion/info.py
    modality detection, acquisition date, pair compatibility

backend/app/ingestion/access.py
    file access used by specialists (replaced by a fake in tests)

backend/app/ingestion/store.py
    upload lookup

backend/app/controller/classifier.py
    keyword query classification

backend/app/controller/router.py
    Router interface; RuleRouter wraps the classifier

backend/app/controller/registry.py
    tool registry: one ToolSpec per task

backend/app/controller/preflight.py
    blocks or warns when the imagery cannot support the task

backend/app/controller/controller.py
    ingestion → routing → preflight → specialist → response
    execution trace

backend/app/models/query.py
    Pydantic request/response schemas, Evidence, SpecialistResult

backend/app/models/params.py
    permitted parameters for each tool

backend/app/analysis/change.py
    change vector analysis

backend/app/analysis/grounding.py
    target extraction from the question, tiling, box merging

backend/app/analysis/sar.py
    speckle filter, water-like mask, bright targets, optical-SAR fusion

backend/app/analysis/masks.py
    threshold and mask cleanup shared by change and SAR

backend/app/analysis/overlay.py
    draws masks and boxes on an image

backend/app/specialists/vqa.py
    BLIP VQA

backend/app/specialists/grounding.py
    OWL-ViT grounding (model not yet run)

backend/app/specialists/change.py
    bi-temporal change detection

backend/app/specialists/sar.py
    SAR analysis and optical-SAR fusion

backend/app/specialists/unknown.py
    unsupported-query fallback

backend/app/reporting/store.py
    saves each analysis

backend/app/reporting/report.py
    builds the HTML report

backend/tests/
    see §18 for the list

frontend/src/App.jsx
    main application UI
    upload
    query
    analysis
    evidence (overlay image, evidence list, report link)
    trace

frontend/src/App.css
    application styling

frontend/src/index.css
    global styling
```

---

# 25. Commit Tracking Template

Every completed milestone should update this section.

| Commit | Feature | Status | Notes |
|---|---|---|---|
| Initial repo commits | Repository setup | COMPLETE | Fork + clone + remotes |
| Ingestion milestone | GeoTIFF ingestion | COMPLETE | Metadata + preview |
| Frontend milestone | Mission-control UI | COMPLETE | React interface |
| Integration milestone | `/analyze` integration | COMPLETE | Frontend ↔ backend |
| Routing milestone | Rule-based controller | COMPLETE | SAR → CHANGE → GROUNDING → VQA |
| `53ca5a7` | BLIP VQA | COMPLETE | CPU inference |
| `93a891c` (PR #2) | Dependency fixes, shared RGB loader, evidence fields, first tests | COMPLETE | VQA now sees the RGB composite |
| `f9a0b9f` (PR #3) | Ingestion checks, tool registry, router interface, preflight | COMPLETE | Classifier kept as the fallback router |
| `39f4935` (PR #4) | Change detection | COMPLETE AS BASELINE | Pixel-level; no learned model |
| `39f4935` (PR #4) | Grounding | UNVERIFIED | OWL-ViT wired in but never executed |
| `39f4935` (PR #4) | Evidence overlays | COMPLETE IN BACKEND | Frontend display not yet confirmed |
| `39f4935` (PR #4) | Reports | COMPLETE AS HTML | No PDF |
| `ac71756` (PR #5) | Optical-SAR | COMPLETE AS BASELINE | Classical; simulated data only |
| Next | Confidence | TODO | Calibration |
| Next | Evaluation | TODO | Held-out benchmark |
| Next | Advanced | TODO | Retrieval/dynamics/etc. |

> Replace/add the actual Git commit SHA beside each row whenever a milestone is committed. Do not invent SHAs in this document.

### What was actually tested (2026-10-07)

- `pytest backend/tests` was run on a team Windows machine after PR #5 was merged and reported no failures. This includes the tests that read real GeoTIFFs and call the API.
- Change detection was also tried on a structured photo with planted changes, a brightness shift, noise and a 1 px misalignment, and found exactly the planted regions.
- SAR analysis has only been run on simulated speckle (1 and 4 looks).

Not yet exercised:

- The OWL-ViT grounding model has never been executed.
- Nothing has been run on real satellite or SAR imagery.
- The Evidence tab and report link have not been confirmed in a browser.
- BLIP VQA has no automated test.

---

# 26. Definition of Done for the Project

The core SatQuery AI prototype should be considered integrated when this end-to-end scenario works:

```text
1. User uploads GeoTIFF
       ↓
2. System validates and inspects raster
       ↓
3. System determines modality/bands/metadata
       ↓
4. User asks natural-language question
       ↓
5. Controller selects task
       ↓
6. Correct specialist is invoked
       ↓
7. Specialist processes image(s)
       ↓
8. System produces answer
       ↓
9. System produces spatial evidence
       ↓
10. System produces calibrated confidence
       ↓
11. System records model/tool + parameters
       ↓
12. UI displays answer + evidence + confidence + trace
       ↓
13. User can download report
```

For the proposal's strongest demonstrated outcome, the demo should cover:

```text
Single image → VQA
Single image → Grounding
Two dates → Change
Optical + SAR → Fusion
```

and visibly demonstrate:

```text
Answer
+
Evidence
+
Confidence
+
Execution Trace
```

---

# 27. Important Scope Rule

The proposal contains both core prototype requirements and advanced additions.

Do not allow advanced features to block the core system.

The implementation order should remain:

```text
Core ingestion
    ↓
Core routing
    ↓
VQA
    ↓
Grounding
    ↓
Change
    ↓
Optical-SAR
    ↓
Evidence
    ↓
Confidence
    ↓
Evaluation
    ↓
Reporting
    ↓
Advanced quantitative methods
    ↓
Retrieval / RAG
    ↓
Object dynamics
    ↓
Domain adaptation
    ↓
Deployment infrastructure
```

**Position as of 2026-10-07:** everything down to Evidence has a working path, with Grounding still to be run once against the real model. Reporting was done early, as HTML. The next steps in this order are Confidence and Evaluation.

A simple, working, evaluated system is more useful than many unfinished integrations.

---

# 28. Proposal Traceability

| Proposal section | Feature | Roadmap section |
|---|---|---|
| 5.1 | Ingestion & compatibility | §3, §12 |
| 5.2 | Agentic controller | §4, §6 |
| 5.3 | Specialist models | §4 |
| 5.4 | Output integration/reporting | §5, §14 |
| 5.5 | Domain adaptation | §15 |
| 5.6 | Agentic orchestration | §4, §16 |
| 5.6 | Retrieval & memory | §10 |
| 5.6 | FastAPI | §3 |
| 5.6 | PostgreSQL/PostGIS | §11 |
| 5.6 | GDAL/Rasterio | §12 |
| 5.6 | MLflow/W&B | §16 |
| 5.6 | Docker/Docker Compose | §17 |
| 5.6 | React + Leaflet/Mapbox | §13 |
| 5.6 | GitHub Actions | §18 |
| 5.6 | Kubernetes | §19 |
| 5.7 | Confidence calibration | §6 |
| 5.7 | Change-point detection | §7 |
| 5.7 | Rolling z-score | §7 |
| 5.7 | EWMA | §7 |
| 5.7 | Ensemble/model risk | §8 |
| 5.7 | Interval uncertainty | §6, §7 |
| 5.7 | Sensitivity analysis | §6 |
| 5.8 | Static object dynamics | §9 |
| 5.8 | Agentive behavior | §9 |
| 5.8 | Scene behavioral signature | §9 |
| 6 | Expected outcomes | §26 |

---

# 29. How to Maintain This File

After every meaningful feature:

1. Implement the feature.
2. Test it locally.
3. Update the relevant `[ ]` → `[x]`.
4. Add the Git commit SHA to §25.
5. Add a short note describing what was actually tested.
6. Push the commit.
7. Do not mark a feature complete merely because its UI exists; mark it complete only when the backend/model path works.

This file is intentionally designed to be the team's running implementation checklist and proposal-to-code traceability document.
