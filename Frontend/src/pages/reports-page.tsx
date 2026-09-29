import { useState } from "react";
import DataTable from "../components/data-table";
import type { Column } from "../components/data-table";
import type { Detection } from "../state/app-types";
import type { AnalysisResult } from "../services/engine8-api";
import { exportAnalysis } from "../services/engine8-api";

const columns: ReadonlyArray<Column<Detection>> = [
  { key: "id", label: "ID", render: (row) => `#${row.id}` },
  { key: "type", label: "Type", render: (row) => row.type },
  { key: "sourceDataset", label: "Dataset", render: (row) => row.sourceDataset ?? "—" },
  { key: "confidence", label: "Confidence", render: (row) => row.confidence === null ? "—" : `${row.confidence}%` },
  { key: "location", label: "Location", render: (row) => `${row.latitude}, ${row.longitude}` },
  { key: "priority", label: "Priority", render: (row) => <span className={`priority-pill priority-${row.priority}`}><i />{row.priority}</span> },
  { key: "status", label: "Status", render: (row) => row.status.replaceAll("-", " ") },
];

export default function ReportsPage({ detections, analysisResult }: { detections: ReadonlyArray<Detection>; analysisResult: AnalysisResult }) {
  const [error, setError] = useState("");
  const reportDetections = detections.slice(0, 5);
  const onExport = () => { try { exportAnalysis(analysisResult, "csv"); setError(""); } catch { setError("CSV export was unavailable. You can still review the analysis table."); } };
  return <div className="page-section"><div className="page-intro"><div><span className="eyebrow">REPORTS · {analysisResult.mode}</span><h2>Detection reports</h2><p>Review up to five records from {analysisResult.filename}, or export the complete backend response.</p></div><button className="primary-button" onClick={onExport}>↓ Export CSV</button></div>{error && <p className="inline-alert" role="alert">{error}</p>}<section className="panel table-panel"><DataTable rows={reportDetections} columns={columns} label="Uploaded scan detection report" /></section>{reportDetections.length === 0 && <p className="muted">The backend returned no detections for this image.</p>}<p className="demo-note">Image ID: {analysisResult.image_id} · {analysisResult.mode} mode</p></div>;
}
