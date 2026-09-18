# SatQuery AI — Project Roadmap, Workflow & Progress Tracker

> **Purpose:** This document is the implementation roadmap for SatQuery AI. It maps the current codebase and Git milestones to the features described in the project proposal, so the team can track what is implemented, what is partially implemented, and what remains.
>
> **Source of truth:** SatQueryAI proposal PDF supplied with the project. This roadmap preserves the proposal's major architecture and feature requirements while turning them into implementation tasks.

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

- [ ] Detect optical vs multispectral vs SAR.
- [ ] Detect/record band semantics where metadata allows.
- [ ] Validate paired-image compatibility.
- [ ] Check spatial dimensions.
- [ ] Check CRS compatibility.
- [ ] Check transform/georeferencing compatibility.
- [ ] Check co-registration.
- [ ] Detect temporal metadata.
- [ ] Support multiple uploaded images cleanly.
- [ ] Return a stable image identifier.
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
- [ ] Render bounding boxes.
- [ ] Render masks.
- [ ] Render change maps.
- [ ] Render optical-SAR overlays.
- [ ] Support selecting multiple datasets.
- [ ] Add report download.
- [ ] Add richer evidence panels.
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
backend/app/controller/classifier.py
```

### Proposal target

The proposal describes an agentic controller where an LLM reads the query plus ingestion information and selects tools from a predefined registry.

### Remaining controller work

- [ ] Add ingestion metadata to routing context.
- [ ] Create formal tool registry.
- [ ] Define permitted parameters for each specialist.
- [ ] Preserve structured routing state.
- [ ] Add LangGraph/LangChain orchestration if justified.
- [ ] Add multi-tool routing for queries requiring more than one capability.
- [ ] Add routing tests.
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
- GeoTIFF first-band loading.
- Numeric normalization.
- RGB conversion.
- BLIP VQA model loading.
- CPU inference.
- Answer generation.
- Execution trace.
- Placeholder system confidence.

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
**Status: STUB**

Current file:

```text
backend/app/specialists/grounding.py
```

Required:

- [ ] Load actual image.
- [ ] Accept referring expressions such as:
      - "Where are the buildings?"
      - "Locate the ships."
      - "Find the road."
- [ ] Run a grounding/localization model.
- [ ] Return bounding boxes and/or masks.
- [ ] Return textual interpretation.
- [ ] Return model score.
- [ ] Produce visual overlay.
- [ ] Persist evidence coordinates.
- [ ] Display evidence in frontend.
- [ ] Add evaluation metrics such as IoU where labelled data exists.

---

## 4.3 Multitemporal Change Understanding
**Status: STUB**

Current file:

```text
backend/app/specialists/change.py
```

Required:

- [ ] Accept two images.
- [ ] Validate that both are compatible.
- [ ] Check spatial alignment / co-registration.
- [ ] Identify acquisition dates where available.
- [ ] Compute baseline change representation.
- [ ] Connect a change-understanding model.
- [ ] Generate change mask/map.
- [ ] Explain detected changes in natural language.
- [ ] Quantify changed area.
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
**Status: STUB**

Current file:

```text
backend/app/specialists/sar.py
```

Required:

- [ ] Accept optical image + SAR image.
- [ ] Validate pair.
- [ ] Validate co-registration.
- [ ] Identify modalities.
- [ ] Normalize optical and SAR inputs appropriately.
- [ ] Connect a joint optical-SAR model.
- [ ] Return textual answer.
- [ ] Return evidence.
- [ ] Return confidence.
- [ ] Visualize paired evidence.
- [ ] Test with Sentinel-1/Sentinel-2 where available.
- [ ] Investigate proposal examples such as EarthMind / Earth-OneVision.

---

## 4.5 Unknown / Unsupported Task
**Status: FUNCTIONAL FALLBACK**

Current file:

```text
backend/app/specialists/unknown.py
```

Keep this.

Required improvements:

- [ ] Explain what information/task is missing.
- [ ] Suggest supported query types.
- [ ] Avoid pretending unsupported analysis was performed.

---

# 5. Evidence-Grounded Output Layer

**Status: PARTIAL**

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

Tasks:

- [ ] Extend Pydantic response models.
- [ ] Define evidence schema.
- [ ] Support bounding boxes.
- [ ] Support masks.
- [ ] Support highlighted regions.
- [ ] Support change maps.
- [ ] Add geospatial coordinates when possible.
- [ ] Render evidence in React.
- [ ] Preserve source-image coordinate system.
- [ ] Make evidence downloadable.

---

# 6. Confidence & Uncertainty Layer

**Status: PARTIAL / PLACEHOLDER**

The current VQA confidence is a temporary system value and should NOT be presented as calibrated model probability.

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

**Status: NOT IMPLEMENTED**

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

- [ ] Calculate changed area.
- [ ] Convert pixel counts to physical area using georeferencing.
- [ ] Report percentage increase/decrease.
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
- [ ] CRS handling.
- [ ] Pixel-to-coordinate conversion.
- [ ] Co-registration checks.
- [ ] Raster alignment.
- [ ] Resampling.
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

**Status: NOT IMPLEMENTED**

Proposal requires a downloadable report containing:

- answer
- supporting visuals
- confidence information
- full execution trace
- selected task
- model/tool used
- parameters applied

Tasks:

- [ ] Define report schema.
- [ ] Generate PDF.
- [ ] Include source metadata.
- [ ] Include query.
- [ ] Include answer.
- [ ] Include evidence image(s).
- [ ] Include confidence.
- [ ] Include uncertainty.
- [ ] Include execution trace.
- [ ] Include model/tool names.
- [ ] Include parameters.
- [ ] Add download endpoint.
- [ ] Add frontend download button.

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
- [ ] Raster dimension limits.
- [ ] Safe upload naming.
- [ ] Avoid arbitrary filesystem paths.
- [ ] Validate all model parameters.
- [ ] Restrict tool parameters.
- [ ] Prevent unsupported tool execution.
- [ ] Error handling around malformed rasters.
- [ ] Model timeout handling.
- [ ] Memory/resource protection.
- [ ] Avoid exposing internal filesystem paths in API responses.

---

# 21. Testing Strategy

## Unit tests

- [ ] Raster metadata extraction.
- [ ] Preview creation.
- [ ] Invalid file rejection.
- [ ] Query classifier.
- [ ] Image resolution.
- [ ] VQA preprocessing.
- [ ] Evidence schema validation.

## Integration tests

- [ ] Upload → inspect.
- [ ] Upload → preview.
- [ ] Upload → analyze → VQA.
- [ ] Two uploads → change.
- [ ] Optical + SAR → fusion.
- [ ] Grounding → overlay.

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
- [ ] Ingestion modality detection.
- [ ] VQA evaluation set.
- [ ] VQA evidence support.

---

## Week 2 — Grounding + Change

### Grounding

- [ ] Actual grounding model.
- [ ] Bounding boxes.
- [ ] Overlay rendering.
- [ ] Grounding API result schema.

### Change

- [ ] Two-image ingestion.
- [ ] Co-registration validation.
- [ ] Change model/baseline.
- [ ] Change mask.
- [ ] Change explanation.
- [ ] Area calculation.

---

## Week 3 — SAR + Evidence + Confidence

### Optical-SAR

- [ ] Pair validation.
- [ ] Optical preprocessing.
- [ ] SAR preprocessing.
- [ ] Fusion model/baseline.
- [ ] Evidence output.

### Evidence

- [ ] Unified evidence schema.
- [ ] Frontend overlays.
- [ ] Coordinates.

### Confidence

- [ ] Collect validation results.
- [ ] Calibrate scores.
- [ ] Display calibrated confidence.
- [ ] Add uncertainty intervals.

---

## Week 4 — Integration + Evaluation + Demo

- [ ] Controller/tool registry.
- [ ] Optional LangGraph integration.
- [ ] Retrieval/FAISS prototype.
- [ ] Report generation.
- [ ] Test suite.
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
- [ ] Grounding
- [ ] Change understanding
- [ ] Optical-SAR pair analysis
- [ ] Evidence overlays
- [ ] Confidence
- [x] Execution trace
- [ ] Multiple image support

## P1 — Strongly recommended

- [ ] LLM/agentic controller
- [ ] Formal tool registry
- [ ] Downloadable report
- [ ] Real map viewer
- [ ] Co-registration checks
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
    upload
    preview
    analyze

backend/app/ingestion/raster.py
    GeoTIFF inspection
    metadata
    preview

backend/app/controller/classifier.py
    query classification

backend/app/controller/controller.py
    routing
    specialist invocation
    execution trace

backend/app/models/query.py
    Pydantic request/response schemas

backend/app/specialists/vqa.py
    BLIP VQA
    GeoTIFF → RGB preprocessing

backend/app/specialists/grounding.py
    grounding placeholder

backend/app/specialists/change.py
    change placeholder

backend/app/specialists/sar.py
    optical-SAR placeholder

backend/app/specialists/unknown.py
    unsupported-query fallback

frontend/src/App.jsx
    main application UI
    upload
    query
    analysis
    evidence
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
| VQA milestone | BLIP VQA | COMPLETE | CPU inference |
| Next | Grounding | TODO | Real localization model |
| Next | Change | TODO | Bi-temporal analysis |
| Next | Optical-SAR | TODO | Paired sensor analysis |
| Next | Evidence | TODO | Boxes/masks/overlays |
| Next | Confidence | TODO | Calibration |
| Next | Reports | TODO | Downloadable report |
| Next | Evaluation | TODO | Held-out benchmark |
| Next | Advanced | TODO | Retrieval/dynamics/etc. |

> Replace/add the actual Git commit SHA beside each row whenever a milestone is committed. Do not invent SHAs in this document.

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
