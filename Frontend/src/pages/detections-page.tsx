import DataTable from "../components/data-table";
import type { Column } from "../components/data-table";
import type { Detection } from "../state/app-types";

type RegisterDetection = Detection & { registerId: number };

type Props = { detections: ReadonlyArray<Detection>; selectedDetectionId: number | null; onSelectDetection: (id: number) => void };
const columns: ReadonlyArray<Column<RegisterDetection>> = [
  { key: "id", label: "ID", render: (row) => <span className="mono">#{String(row.registerId).padStart(2, "0")}</span> },
  { key: "type", label: "Type", render: (row) => row.type },
  { key: "sourceDataset", label: "Dataset", render: (row) => row.sourceDataset ?? "—" },
  { key: "confidence", label: "Confidence", render: (row) => row.confidence === null ? "—" : `${row.confidence}%` },
  { key: "location", label: "Location", render: (row) => `${row.latitude}, ${row.longitude}` },
  { key: "priority", label: "Priority", render: (row) => <span className={`priority-pill priority-${row.priority}`}><i />{row.priority}</span> },
  { key: "status", label: "Status", render: (row) => row.status.replaceAll("-", " ") },
];

export default function DetectionsPage({ detections, selectedDetectionId, onSelectDetection }: Props) {
  const registerDetections: ReadonlyArray<RegisterDetection> = detections.slice(0, 5).map((detection, index) => ({ ...detection, registerId: index + 1 }));
  return <div className="page-section"><div className="page-intro"><div><span className="eyebrow">{registerDetections.length} RECORDS · UPLOADED SCAN</span><h2>Detection register</h2><p>Select a row to open its sonar evidence.</p></div><span className="live-indicator">ANALYSIS OUTPUT</span></div><section className="panel table-panel"><DataTable rows={registerDetections} columns={columns} selectedId={selectedDetectionId} onSelect={(row) => onSelectDetection(row.id)} label="Uploaded scan detection register" /></section>{registerDetections.length === 0 && <p className="muted">No detection records were returned by the backend for this image.</p>}</div>;
}
