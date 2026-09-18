import { useRef, useState } from "react";
import "./App.css";

const suggestions = [
  "What objects are visible in this image?",
  "Identify the major built-up areas.",
  "Are there any changes between these images?",
  "Locate vehicles or other moving objects.",
];

function App() {
  const fileInputRef = useRef(null);

  const [files, setFiles] = useState([]);
  const [query, setQuery] = useState("");
  const [activeMode, setActiveMode] = useState("image");
  const [activeTab, setActiveTab] = useState("analysis");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const [imageData, setImageData] = useState(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const modeIndex = {
    image: 0,
    map: 1,
    split: 2,
  };

  const tabIndex = {
    analysis: 0,
    evidence: 1,
    trace: 2,
  };

  const handleFileSelect = async (event) => {
    const selectedFiles = Array.from(event.target.files || []);

    const validFiles = selectedFiles.filter((file) =>
      /\.(tif|tiff)$/i.test(file.name)
    );

    event.target.value = "";

    if (!validFiles.length) {
      setUploadError("Please select a GeoTIFF or TIFF file.");
      return;
    }

    setIsUploading(true);
    setUploadError("");

    try {
      const uploadedResults = [];

      for (const file of validFiles) {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(
          "http://127.0.0.1:8000/inspect-raster",
          {
            method: "POST",
            body: formData,
          }
        );

        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.detail || `Unable to upload ${file.name}`);
        }

        uploadedResults.push({
          file,
          ...result,
          previewUrl: `http://127.0.0.1:8000/preview/${encodeURIComponent(
            result.preview
          )}`,
        });
      }

      setFiles((current) => [...current, ...validFiles]);
      setImageData(uploadedResults[0]);
    } catch (error) {
      setUploadError(error.message || "Unable to upload imagery.");
    } finally {
      setIsUploading(false);
    }
  };

  const removeFile = (index) => {
    setFiles((current) => {
      const nextFiles = current.filter((_, i) => i !== index);

      if (index === 0) {
        setImageData(null);
      }

      return nextFiles;
    });
  };

  const handleSuggestion = (suggestion) => {
    setQuery(suggestion);
  };

  const handleAnalyze = async () => {
  if (!query.trim() || !files.length || isAnalyzing) {
    return;
  }

  setIsAnalyzing(true);
  setAnalysisError("");
  setAnalysisResult(null);
  setActiveTab("analysis");

  try {
    const requestBody = {
      query: query.trim(),
      image_id: imageData?.filename || files[0]?.name || null,
      image_id_2: files.length > 1 ? files[1]?.name || null : null,
    };

    const response = await fetch(
      "http://127.0.0.1:8000/analyze",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      }
    );

    const result = await response.json();

    if (!response.ok) {
      throw new Error(
        result.detail || "Analysis request failed."
      );
    }

    setAnalysisResult(result);
  } catch (error) {
    console.error("Analysis error:", error);

    setAnalysisError(
      error.message || "Unable to analyze the imagery."
    );
  } finally {
    setIsAnalyzing(false);
  }
};

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <span />
            <span />
            <span />
          </div>

          <div>
            <div className="brand-name">SATQUERY</div>

            <div className="brand-subtitle">
              REMOTE SENSING INTELLIGENCE
            </div>
          </div>
        </div>

        <div className="system-status">
          <span className="live-dot" />
          <span>SYSTEM READY</span>
        </div>

        <div className="topbar-actions">
          <button className="topbar-button">
            HISTORY <span className="counter">0</span>
          </button>

          <button className="topbar-button">
            SETTINGS
          </button>

          <div className="avatar">
            SQ
          </div>
        </div>
      </header>

      <main className="workspace">
        <aside className="sidebar">
          <div className="sidebar-scroll">
            <section className="sidebar-section">
              <div className="section-heading">
                <span>DATA SOURCES</span>
                <strong>{files.length}</strong>
              </div>

              <button
                className="upload-button"
                onClick={() => fileInputRef.current?.click()}
              >
                <span className="upload-symbol">
                  +
                </span>

                <span>
                  <strong>Upload imagery</strong>
                  <small>GeoTIFF / TIFF</small>
                </span>
              </button>

              <input
                ref={fileInputRef}
                type="file"
                accept=".tif,.tiff"
                multiple
                onChange={handleFileSelect}
                hidden
              />

              {uploadError && (
                <div className="upload-error">{uploadError}</div>
              )}

              <div className="file-list">
                {files.length === 0 ? (
                  <div className="empty-files">
                    <div className="empty-files-icon">
                      ⌁
                    </div>

                    <strong>
                      No imagery loaded
                    </strong>

                    <span>
                      Add satellite imagery to initialize the workspace.
                    </span>
                  </div>
                ) : (
                  files.map((file, index) => (
                    <div
                      className="file-card"
                      key={`${file.name}-${index}`}
                    >
                      <div className="file-type">
                        TIF
                      </div>

                      <div className="file-info">
                        <strong>
                          {file.name}
                        </strong>

                        <span>
                          {formatFileSize(file.size)}
                        </span>
                      </div>

                      <button
                        className="remove-file"
                        onClick={() => removeFile(index)}
                      >
                        ×
                      </button>
                    </div>
                  ))
                )}
              </div>
            </section>

            <div className="sidebar-rule" />

            <section className="sidebar-section">
              <div className="section-heading">
                <span>IMAGE CONTEXT</span>
              </div>

              <div className="metadata-grid">
                <Metadata
                  label="MODALITY"
                  value={imageData ? "RASTER" : "—"}
                />

                <Metadata
                  label="BANDS"
                  value={imageData ? imageData.metadata.bands : "—"}
                />

                <Metadata
                  label="CRS"
                  value={imageData ? imageData.metadata.crs : "—"}
                />

                <Metadata
                  label="STATUS"
                  value={isUploading ? "PROCESSING" : files.length ? "READY" : "WAITING"}
                />
              </div>
            </section>

            <div className="sidebar-rule" />

            <section className="sidebar-section">
              <div className="section-heading">
                <span>CAPABILITIES</span>
              </div>

              <div className="capability-list">
                <Capability
                  label="Visual Question Answering"
                  code="VQA"
                />

                <Capability
                  label="Visual Grounding"
                  code="GRD"
                />

                <Capability
                  label="Change Understanding"
                  code="CHG"
                />

                <Capability
                  label="Optical + SAR Fusion"
                  code="SAR"
                />
              </div>
            </section>
          </div>

          <div className="sidebar-footer">
            <div className="engine-status">
              <span className="live-dot small" />

              <div>
                <strong>
                  SatQuery Engine
                </strong>

                <small>
                  Multimodal analysis
                </small>
              </div>
            </div>

            <span className="version">
              v0.1
            </span>
          </div>
        </aside>

        <section className="console">
          <div className="console-grid">
            <section className="viewer-column">
              <div className="panel-header">
                <div>
                  <span className="eyebrow">
                    ANALYSIS WORKSPACE
                  </span>

                  <h1>
                    Satellite Intelligence
                  </h1>
                </div>

                <div
                  className="mode-switcher"
                  style={{
                    "--mode-index": modeIndex[activeMode],
                  }}
                >
                  {["image", "map", "split"].map((mode) => (
                    <button
                      key={mode}
                      className={
                        activeMode === mode
                          ? "active"
                          : ""
                      }
                      onClick={() =>
                        setActiveMode(mode)
                      }
                    >
                      {mode.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              <div className={`viewer viewer-${activeMode}`}>
                {activeMode === "split" ? (
                  <div className="split-view">
                    <RasterCanvas
                      files={files}
                      label="OPTICAL"
                      imageData={imageData}
                    />

                    <RasterCanvas
                      files={files}
                      label="MAP / GEOREFERENCE"
                      imageData={imageData}
                    />
                  </div>
                ) : (
                  <RasterCanvas
                    files={files}
                    imageData={imageData}
                    label={
                      activeMode === "map"
                        ? "MAP VIEW"
                        : "RASTER PREVIEW"
                    }
                    map={activeMode === "map"}
                  />
                )}

                <div className="viewer-toolbar">
                  <button>+</button>
                  <button>−</button>
                  <span />
                  <button>FIT</button>
                </div>

                <div className="viewer-scale">
                  100 m
                </div>
              </div>

              <div className="viewer-statusbar">
                <span>
                  SOURCE{" "}
                  <strong>
                    {files.length
                      ? files[0].name
                      : "NO DATASET"}
                  </strong>
                </span>

                <span>
                  RESOLUTION{" "}
                  <strong>
                    {imageData
                      ? `${imageData.metadata.width} × ${imageData.metadata.height} px`
                      : "—"}
                  </strong>
                </span>

                <span>
                  COORDINATES{" "}
                  <strong>
                    {imageData
                      ? `${imageData.metadata.bounds.left.toFixed(4)}, ${imageData.metadata.bounds.bottom.toFixed(4)}`
                      : "—"}
                  </strong>
                </span>

                <span className="viewer-ready">
                  <i />
                  VIEWER READY
                </span>
              </div>
            </section>

            <section className="analysis-column">
              <div className="query-panel">
                <div className="query-heading">
                  <span className="eyebrow">
                    NATURAL LANGUAGE QUERY
                  </span>

                  <h2>
                    Ask SatQuery AI
                  </h2>
                </div>

                <div className="query-box">
                  <textarea
                    value={query}
                    onChange={(event) =>
                      setQuery(event.target.value)
                    }
                    placeholder="Ask anything about the satellite imagery..."
                    rows={5}
                  />

                  <div className="query-footer">
                    <span>
                      {files.length
                        ? `${files.length} DATA SOURCE${
                            files.length > 1
                              ? "S"
                              : ""
                          } CONNECTED`
                        : "NO DATA SOURCE CONNECTED"}
                    </span>

                    <button
                      className="analyze-button"
                      disabled={
                        !query.trim() ||
                        !files.length ||
                        isAnalyzing
                      }
                      onClick={handleAnalyze}
                    >
                      {isAnalyzing ? (
                        <>
                          <span className="spinner" />
                          ANALYZING
                        </>
                      ) : (
                        <>
                          ANALYZE
                          <span>→</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

                <div className="suggestions">
                  <span className="try-label">
                    TRY ASKING
                  </span>

                  {suggestions.slice(0, 3).map(
                    (suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() =>
                          handleSuggestion(
                            suggestion
                          )
                        }
                      >
                        {suggestion}
                      </button>
                    )
                  )}
                </div>
              </div>

              <div className="results-panel">
                <div className="results-header">
                  <div
                    className="result-tabs"
                    style={{
                      "--tab-index":
                        tabIndex[activeTab],
                    }}
                  >
                    <button
                      className={
                        activeTab === "analysis"
                          ? "active"
                          : ""
                      }
                      onClick={() =>
                        setActiveTab("analysis")
                      }
                    >
                      ANALYSIS
                    </button>

                    <button
                      className={
                        activeTab === "evidence"
                          ? "active"
                          : ""
                      }
                      onClick={() =>
                        setActiveTab("evidence")
                      }
                    >
                      EVIDENCE
                    </button>

                    <button
                      className={
                        activeTab === "trace"
                          ? "active"
                          : ""
                      }
                      onClick={() =>
                        setActiveTab("trace")
                      }
                    >
                      EXECUTION TRACE
                    </button>
                  </div>

                  <button
                    className="details-button"
                    onClick={() =>
                      setShowDetails(
                        (value) => !value
                      )
                    }
                  >
                    {showDetails
                      ? "HIDE"
                      : "DETAILS"}
                  </button>
                </div>

                {activeTab === "analysis" && (
                <>
                  <div className="analysis-state">
                    <div className="state-icon">
                      ✦
                    </div>

                    <div>
                      <span className="state-label">
                        ANALYSIS STATUS
                      </span>

                      <h3>
                        {isAnalyzing
                          ? "Processing query..."
                          : analysisError
                          ? "Analysis failed"
                          : analysisResult
                          ? "Analysis complete"
                          : "Awaiting analysis"}
                      </h3>

                      <p>
                        {isAnalyzing
                          ? "The controller is classifying your query and selecting the appropriate specialist capability."
                          : analysisError
                          ? analysisError
                          : analysisResult
                          ? analysisResult.answer
                          : "The controller will classify your question and select the appropriate specialist capability."}
                      </p>
                    </div>
                  </div>

                  <div className="metrics">
                    <Metric
                      label="TASK"
                      value={
                        analysisResult?.task || "AUTO ROUTE"
                      }
                    />

                    <Metric
                      label="MODEL"
                      value={
                        analysisResult
                          ? `${analysisResult.task} SPECIALIST`
                          : "—"
                      }
                    />

                    <Metric
                      label="CONFIDENCE"
                      value={
                        analysisResult
                          ? `${Math.round(
                              analysisResult.confidence * 100
                            )}%`
                          : "—"
                      }
                    />

                    <Metric
                      label="EVIDENCE"
                      value={
                        analysisResult
                          ? "GENERATED"
                          : "PENDING"
                      }
                    />
                  </div>

                  <TracePreview
                    analysisResult={analysisResult}
                    isAnalyzing={isAnalyzing}
                  />
                </>
              )}

                {activeTab === "evidence" && (
                  <div className="empty-result">
                    <div className="state-icon">
                      ⌖
                    </div>

                    <h3>
                      No evidence generated
                    </h3>

                    <p>
                      Visual highlights, bounding boxes
                      and masks will appear here after an
                      analysis is completed.
                    </p>

                    <TracePreview />
                  </div>
                )}

                {activeTab === "trace" && (
                  <div className="trace">
                    {analysisResult?.execution_trace?.length ? (
                      analysisResult.execution_trace.map((item, index) => (
                        <TraceStep
                          key={`${item.step}-${index}`}
                          number={String(index + 1).padStart(2, "0")}
                          title={item.step}
                          description={
                            item.status === "stub"
                              ? "Specialist execution is currently using a placeholder."
                              : item.status === "warning"
                              ? "The controller could not confidently route this request."
                              : "Step completed successfully."
                          }
                          status={item.status}
                        />
                      ))
                    ) : (
                      <>
                        <TraceStep
                          number="01"
                          title="Image ingestion"
                          description="Parse format, bands, modality and metadata"
                          status="waiting"
                        />

                        <TraceStep
                          number="02"
                          title="Query classification"
                          description="Determine the required analysis task"
                          status="waiting"
                        />

                        <TraceStep
                          number="03"
                          title="Specialist selection"
                          description="Select the appropriate model or tool"
                          status="waiting"
                        />

                        <TraceStep
                          number="04"
                          title="Evidence generation"
                          description="Generate spatial and textual evidence"
                          status="waiting"
                        />

                        <TraceStep
                          number="05"
                          title="Output integration"
                          description="Combine answer, confidence and evidence"
                          status="waiting"
                        />
                      </>
                    )}
                  </div>
                )}

                {showDetails && (
                  <div className="details-panel">
                    <span className="eyebrow">
                      SYSTEM INFORMATION
                    </span>

                    <p>
                      SatQuery AI uses the ingestion
                      layer to establish image
                      compatibility before routing the
                      natural-language query to
                      specialist analysis tools.
                    </p>
                  </div>
                )}
              </div>
            </section>
          </div>
        </section>
      </main>
    </div>
  );
}

function RasterCanvas({
  files,
  label,
  imageData,
  map = false,
}) {
  return (
    <div
      className={`raster-canvas ${
        map ? "map-canvas" : ""
      }`}
    >
      <div className="coordinate-frame">
        <span className="axis-top" />
        <span className="axis-right" />
        <span className="axis-bottom" />
        <span className="axis-left" />

        <div className="tick top-ticks" />
        <div className="tick bottom-ticks" />
        <div className="tick left-ticks" />
        <div className="tick right-ticks" />
      </div>

      <div className="terrain-grid" />

      {files.length === 0 ? (
        <div className="canvas-empty">
          <div className="target-icon">
            <span />
          </div>

          <span className="canvas-code">
            RASTER INPUT / 00
          </span>

          <strong>
            Awaiting imagery
          </strong>

          <p>
            Upload a GeoTIFF or TIFF dataset to
            initialize the viewer.
          </p>
        </div>
      ) : (
        <div className="loaded-placeholder">
          {imageData?.previewUrl ? (
            <img
              className="raster-image"
              style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }}
              src={imageData.previewUrl}
              alt={imageData.filename}
            />
          ) : null}

          <div className="scan-line" />

          <div className="raster-label">
            <span>{label}</span>

            <strong>
              {imageData?.filename || files[0].name}
            </strong>
          </div>

          {!imageData?.previewUrl && (
            <div className="raster-center">
              <span>
                RASTER DATA
              </span>

              <strong>
                PROCESSING READY
              </strong>
            </div>
          )}
        </div>
      )}

      <div className="canvas-corner top-left-corner">
        N ↑
      </div>

      <div className="canvas-corner top-right-corner">
        EPSG: {imageData?.metadata?.crs || "—"}
      </div>

      <div className="canvas-corner bottom-left-corner">
        LAT {imageData ? imageData.metadata.bounds.bottom.toFixed(4) : "—"}
      </div>

      <div className="canvas-corner bottom-right-corner">
        LON {imageData ? imageData.metadata.bounds.left.toFixed(4) : "—"}
      </div>
    </div>
  );
}

function TracePreview({
  analysisResult,
  isAnalyzing,
}) {
  const trace = analysisResult?.execution_trace || [];

  return (
    <div className="trace-preview">
      <div className="trace-preview-header">
        <span className="trace-preview-title">
          EXECUTION PIPELINE
        </span>

        <span className="trace-preview-state">
          {isAnalyzing
            ? "RUNNING"
            : analysisResult
            ? "COMPLETE"
            : "IDLE"}
        </span>
      </div>

      {analysisResult ? (
        <div className="trace-result-list">
          {trace.map((item, index) => (
            <div
              className="trace-result-item"
              key={`${item.step}-${index}`}
            >
              <span className="trace-result-number">
                {String(index + 1).padStart(2, "0")}
              </span>

              <span className="trace-result-step">
                {item.step}
              </span>

              <span className="trace-result-status">
                {item.status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="trace-stepper">
            <span className="trace-node" />

            <span className="trace-line" />

            <span className="trace-node" />

            <span className="trace-line" />

            <span className="trace-node" />

            <span className="trace-line" />

            <span className="trace-node" />

            <span className="trace-line" />

            <span className="trace-node" />
          </div>

          <div className="trace-step-labels">
            <span>INGEST</span>
            <span>ROUTE</span>
            <span>MODEL</span>
            <span>EVIDENCE</span>
            <span>REPORT</span>
          </div>
        </>
      )}
    </div>
  );
}

function Metadata({
  label,
  value,
}) {
  return (
    <div className="metadata-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Capability({
  label,
  code,
}) {
  return (
    <div className="capability">
      <span>{code}</span>
      <strong>{label}</strong>
    </div>
  );
}

function Metric({
  label,
  value,
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function TraceStep({
  number,
  title,
  description,
  status = "waiting",
}) {
  const normalizedStatus = status.toLowerCase();

  const statusLabel =
    normalizedStatus === "complete"
      ? "COMPLETE"
      : normalizedStatus === "stub"
      ? "STUB"
      : normalizedStatus === "warning"
      ? "WARNING"
      : normalizedStatus === "running"
      ? "RUNNING"
      : "WAITING";

  return (
    <div className={`trace-step trace-${normalizedStatus}`}>
      <div className="trace-marker">
        <span>{number}</span>
      </div>

      <div className="trace-content">
        <strong>{title}</strong>
        <small>{description}</small>
      </div>

      <span className="trace-waiting">
        {statusLabel}
      </span>
    </div>
  );
}

function formatFileSize(bytes) {
  if (!bytes) {
    return "0 KB";
  }

  const mb = bytes / (1024 * 1024);

  if (mb >= 1) {
    return `${mb.toFixed(2)} MB`;
  }

  return `${Math.max(
    1,
    Math.round(bytes / 1024)
  )} KB`;
}

export default App;