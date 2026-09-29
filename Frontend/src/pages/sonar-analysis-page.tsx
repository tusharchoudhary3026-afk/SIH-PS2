import { useEffect, useState } from "react";
import SonarViewer from "../components/sonar-viewer";
import DetectionDetailPanel from "../components/detection-detail-panel";
import EvidenceCard from "../components/evidence-card";
import type { AnalysisPreferences, Detection } from "../state/app-types";
import { analyzeImage, exportAnalysis, getApiHealth, saveReview, type AnalysisDetection, type AnalysisResult, type ApiHealth } from "../services/engine8-api";

type Props = {
  detections: ReadonlyArray<Detection>;
  selectedDetectionId: number | null;
  onSelectDetection: (id: number) => void;
  preferences: AnalysisPreferences;
  onPreferencesChange: (preferences: AnalysisPreferences) => void;
  analysisResult: AnalysisResult | null;
  onAnalysisResult: (result: AnalysisResult | null) => void;
};

export default function SonarAnalysisPage({ detections, selectedDetectionId, onSelectDetection, preferences, onPreferencesChange, analysisResult, onAnalysisResult }: Props) {
  const [zoom, setZoom] = useState(100);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState("");
  const [validationError, setValidationError] = useState("");
  const [analysisState, setAnalysisState] = useState<"idle" | "running" | "complete">("idle");
  const [scanMode, setScanMode] = useState("");
  const [apiHealth, setApiHealth] = useState<ApiHealth | null>(null);
  const [reviewMessage, setReviewMessage] = useState("");
  const [selectedApiId, setSelectedApiId] = useState<string | null>(null);
  const [cropUrl, setCropUrl] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    void getApiHealth().then((health) => { if (current) setApiHealth(health); }).catch(() => {
      if (current) setApiHealth({ status: "unavailable", mode: "UNAVAILABLE", engine4: "UNKNOWN", subpipe: "UNKNOWN" });
    });
    return () => { current = false; };
  }, []);
  useEffect(() => () => { if (imageUrl) URL.revokeObjectURL(imageUrl); }, [imageUrl]);

  const selected = detections.find((item) => item.id === selectedDetectionId);
  const selectedApi = analysisResult?.detections.find((item) => item.detection_id === selectedApiId) ?? analysisResult?.detections[0];
  const selectApiDetection = (id: string) => {
    setSelectedApiId(id);
    const index = analysisResult?.detections.findIndex((item) => item.detection_id === id) ?? -1;
    if (index >= 0) onSelectDetection(index + 1);
  };
  const runAnalysis = async (file: File) => {
    setAnalysisState("running");
    setUploadError("");
    setValidationError("");
    setReviewMessage("");
    setSelectedApiId(null);
    onAnalysisResult(null);
    try {
      const result = await analyzeImage(file);
      onAnalysisResult(result);
      setAnalysisState("complete");
    } catch (error) {
      setAnalysisState("idle");
      setUploadError(`Analysis could not be completed: ${error instanceof Error ? error.message : "backend unavailable"}`);
    }
  };
  const onUpload = (file?: File) => {
    if (!file) return;
    setUploadError("");
    setValidationError("");
    if (!file.type.startsWith("image/")) { setSelectedFile(null); setUploadError("Choose an image file to scan."); return; }
    try {
      const nextUrl = URL.createObjectURL(file);
      setImageUrl((previous) => { if (previous) URL.revokeObjectURL(previous); return nextUrl; });
      setSelectedFile(file);
      setAnalysisState("idle");
      onAnalysisResult(null);
    } catch {
      setUploadError("This image could not be opened. Try another image file.");
    }
  };
  const onImageError = () => setUploadError("The selected image could not be previewed.");
  const startScan = () => {
    const missing: string[] = [];
    if (!selectedFile) missing.push("upload an image");
    if (!scanMode) missing.push("select a scan mode");
    if (missing.length) {
      setValidationError(`Before scanning, ${missing.join(" and ")}.`);
      return;
    }
    void runAnalysis(selectedFile!);
  };
  const resetScan = () => {
    setImageUrl((previous) => { if (previous) URL.revokeObjectURL(previous); return null; });
    setSelectedFile(null);
    setAnalysisState("idle");
    setUploadError("");
    setValidationError("");
    setScanMode("");
    setReviewMessage("");
    setSelectedApiId(null);
    onAnalysisResult(null);
  };
  const togglePreference = (key: "showDetections" | "showAcousticShadows") => onPreferencesChange({ ...preferences, [key]: !preferences[key] });
  const datasetGroups = analysisResult ? [...new Set(analysisResult.detections.map((item) => item.source_dataset))].map((dataset) => ({
    dataset,
    detections: analysisResult.detections.filter((item) => item.source_dataset === dataset),
  })) : [];
  const review = async (action: "confirm" | "reject" | "flag", detectionId: string) => {
    try {
      const saved = await saveReview(detectionId, action);
      const updated = analysisResult ? {
        ...analysisResult,
        detections: analysisResult.detections.map((row) => row.detection_id === detectionId ? { ...row, human_review: saved.human_review } : row),
      } : null;
      if (updated) onAnalysisResult(updated);
      setReviewMessage(`Review saved: ${action}.`);
    } catch (error) {
      setReviewMessage(`Review could not be saved: ${error instanceof Error ? error.message : "API unavailable"}`);
    }
  };
  useEffect(() => {
    if (!imageUrl || !selectedApi || !analysisResult) { setCropUrl(null); return; }
    let cancelled = false;
    const image = new Image();
    image.onload = () => {
      const [x1, y1, x2, y2] = selectedApi.bbox;
      const left = Math.max(0, Math.floor(x1));
      const top = Math.max(0, Math.floor(y1));
      const width = Math.min(image.naturalWidth, Math.ceil(x2)) - left;
      const height = Math.min(image.naturalHeight, Math.ceil(y2)) - top;
      if (cancelled || width < 1 || height < 1) { setCropUrl(null); return; }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) { setCropUrl(null); return; }
      context.drawImage(image, left, top, width, height, 0, 0, width, height);
      setCropUrl(canvas.toDataURL("image/png"));
    };
    image.onerror = () => setCropUrl(null);
    image.src = imageUrl;
    return () => { cancelled = true; };
  }, [imageUrl, selectedApi, analysisResult]);

  if (!analysisResult) {
    return <div className="analysis-page page-section">
      <section className="scan-upload-state panel">
        <div className="upload-copy"><span className="eyebrow">NEW SONAR SURVEY · ENGINE 8</span><h2>Upload a sonar image</h2><p>Choose an image, select Full analysis, then start the scan. The review workspace and report sections appear when analysis completes.</p></div>
        <div className="scan-upload-controls">
          <label className={`scan-upload-drop${selectedFile ? " has-file" : ""}`}><input type="file" accept="image/*" disabled={analysisState === "running"} onChange={(event) => { onUpload(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} /><span className="upload-icon">↑</span><strong>{selectedFile ? selectedFile.name : "Choose a sonar image"}</strong><small>{selectedFile ? "Image ready. Scanning starts only when you press the button below." : "PNG, JPEG, TIFF, or another supported image format"}</small></label>
          <label className="dataset-select"><span>Scan mode <b aria-hidden="true">Required</b></span><select required value={scanMode} disabled={analysisState === "running"} aria-invalid={Boolean(validationError && !scanMode)} onChange={(event) => { setScanMode(event.currentTarget.value); setValidationError(""); }}><option value="">Select a scan mode</option><option value="FULL">Full analysis</option></select></label>
          <button className="primary-button start-scan-button" type="button" disabled={analysisState === "running"} onClick={startScan}>{analysisState === "running" ? "Scanning image…" : "Start scanning"}<span>→</span></button>
          {analysisState === "running" && <p className="scan-progress" role="status"><span className="scan-spinner" /> Uploading and analyzing image…</p>}
          {validationError && <p className="inline-alert" role="alert">{validationError}</p>}
          {uploadError && <p className="inline-alert" role="alert">{uploadError}</p>}
          <p className="api-connection">Backend: <strong>{apiHealth?.status === "ok" ? `${apiHealth.mode} mode` : "not reachable"}</strong><span> · </span><code>POST /api/analyze</code></p>
        </div>
      </section>
    </div>;
  }

  return <div className="analysis-page page-section">
    <div className="page-intro"><div><span className="eyebrow">UPLOAD ANALYSIS · {analysisResult.filename}</span><h2>Review the seafloor return</h2><p>Review the detections and evidence returned for this uploaded image.</p></div><div className="control-row"><span className={`analysis-status ${analysisState === "complete" ? "complete" : ""}`}>ANALYSIS COMPLETE · {analysisResult.mode}</span><label className="upload-button">↑ New Scan<input type="file" accept="image/*" onChange={(event) => { onUpload(event.currentTarget.files?.[0]); event.currentTarget.value = ""; }} /></label></div></div>
    {analysisResult.mode === "MOCK" && <p className="mock-mode-banner" role="status">MOCK SAMPLE DATA · Ghost Net, Metal Debris, and Cable rows are synthetic placeholders. Their locations do not come from this image, so image boxes and sample crops are hidden.</p>}
    <div className="analysis-layout"><section className="analysis-main">
      <SonarViewer detections={detections} selectedDetectionId={selectedDetectionId} onSelectDetection={onSelectDetection} preferences={preferences} imageUrl={imageUrl} imageLabel={analysisResult.filename} onImageError={onImageError} zoom={zoom} compare={false} apiDetections={analysisResult.detections} apiImageSize={{ width: analysisResult.image_width, height: analysisResult.image_height }} showApiDetections={analysisResult.mode === "REAL"} onSelectApiDetection={selectApiDetection} />
      <div className="control-deck"><div className="control-row"><button className="secondary-button" onClick={resetScan}>← Upload another image</button><button className="toggle-button" aria-pressed={preferences.showDetections} onClick={() => togglePreference("showDetections")}>Detection overlay <b>{preferences.showDetections ? "ON" : "OFF"}</b></button><button className="toggle-button" disabled title="The API returns shadow evidence values, not a shadow mask overlay.">Acoustic shadow <b>API EVIDENCE</b></button><button className="toggle-button" disabled title="A second survey is required for comparison.">Compare <b>NEEDS BASELINE</b></button><div className="zoom-control"><button aria-label="Zoom out" onClick={() => setZoom(Math.max(50, zoom - 10))}>−</button><span>{zoom}%</span><button aria-label="Zoom in" onClick={() => setZoom(Math.min(200, zoom + 10))}>+</button></div></div></div>
      <section className="api-result panel"><div className="section-heading"><div><span className="eyebrow">{analysisResult.mode} · {analysisResult.datasets?.join(" + ") || analysisResult.source_dataset}</span><h3>Engine results</h3></div><div className="control-row"><button className="secondary-button" onClick={() => exportAnalysis(analysisResult, "json")}>Export JSON</button><button className="secondary-button" onClick={() => exportAnalysis(analysisResult, "csv")}>Export CSV</button></div></div><p>{analysisResult.message ?? analysisResult.detector_status} · {analysisResult.detections.length} detections · {analysisResult.image_width} × {analysisResult.image_height}px</p>
        {analysisResult.detections.length === 0 ? <div className="empty-analysis"><strong>No detections returned for this image.</strong><p>The frontend is showing the backend response as received; it does not fill in demo detections.</p></div> : <>{analysisResult.mode !== "MOCK" && cropUrl && <figure><img className="evidence-crop" src={cropUrl} alt="Crop for selected detector result" /><figcaption>Selected crop · {selectedApi?.class_name}</figcaption></figure>}{datasetGroups.map((group) => <section className="dataset-result-group" key={group.dataset}><div className="dataset-result-heading"><span className="eyebrow">SOURCE DATASET</span><strong>{group.dataset}</strong><span>{group.detections.length} {group.detections.length === 1 ? "detection" : "detections"}</span></div>{[...group.detections].sort((left, right) => (right.inspection_priority.score ?? -1) - (left.inspection_priority.score ?? -1)).map((item: AnalysisDetection) => <article className="api-detection-detail" key={item.detection_id}><strong>{item.class_name}</strong><span className="dataset-badge">{item.source_dataset}{analysisResult.mode === "MOCK" ? " · MOCK SAMPLE" : ""}</span><p>Raw detector score: {item.raw_confidence.toFixed(3)} · Calibrated confidence: {item.calibrated_confidence === null ? "Unavailable" : item.calibrated_confidence.toFixed(3)} ({item.confidence_status})</p><p>Shadow consistency: {item.shadow_consistency?.toFixed(3) ?? "Unavailable"} · Local contrast: {item.local_contrast?.toFixed(3) ?? "Unavailable"} · Aspect ratio: {item.aspect_ratio.toFixed(3)}</p><p>Geolocation: {item.geolocation_type}{item.latitude !== null && item.longitude !== null ? ` · ${item.latitude}, ${item.longitude}` : " · unavailable"} · {item.geolocation_status}</p><p>Inspection priority: {item.inspection_priority.band} · {item.inspection_priority.score?.toFixed(3) ?? "Unavailable"} · review {item.human_review.status}</p><div className="control-row"><button className="secondary-button" onClick={() => { setSelectedApiId(item.detection_id); void review("confirm", item.detection_id); }}>Confirm</button><button className="secondary-button" onClick={() => { setSelectedApiId(item.detection_id); void review("reject", item.detection_id); }}>Reject</button><button className="secondary-button" onClick={() => { setSelectedApiId(item.detection_id); void review("flag", item.detection_id); }}>Flag for review</button></div></article>)}</section>)}</>}{reviewMessage && <p role="status">{reviewMessage}</p>}</section>
      <section className="evidence-section"><div className="section-heading"><div><span className="eyebrow">ENGINE EVIDENCE</span><h2>Why was this detected?</h2></div></div>{selected ? <div className="evidence-grid">{selected.evidence.map((item, index) => <EvidenceCard key={item.label} index={`0${index + 1}`} label={item.label} description={item.description} />)}</div> : <p className="empty-analysis">No detection evidence is available for this scan.</p>}</section>
    </section><aside className="analysis-aside"><DetectionDetailPanel detection={selected} /><div className="panel scan-context"><span className="eyebrow">UPLOADED IMAGE</span><h3>{analysisResult.filename}</h3><p>Image ID: {analysisResult.image_id}<br />Dimensions: {analysisResult.image_width} × {analysisResult.image_height}px<br />Datasets: {analysisResult.datasets?.join(", ") ?? analysisResult.source_dataset}</p><span className="context-badge">{analysisResult.detector_status}</span><p className="demo-note">{analysisResult.location_policy}</p></div></aside></div>
  </div>;
}
