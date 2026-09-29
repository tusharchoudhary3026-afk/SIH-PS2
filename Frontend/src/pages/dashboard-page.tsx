import SonarDashboardIntro from "../components/sonar-dashboard-intro";
import DataTable from "../components/data-table";
import type { Column } from "../components/data-table";
import type { Detection } from "../state/app-types";
import { demoDetections } from "../state/demo-data";
import type { AnalysisResult } from "../services/engine8-api";

type Props = { detections: ReadonlyArray<Detection>; analysisResult: AnalysisResult | null; onViewSonar: () => void; onSelectDetection: (id: number) => void };
const demoMetrics = [
  { label: "Total scans", value: "128", tone: "default" },
  { label: "Detections", value: "37", tone: "default" },
  { label: "High priority", value: "08", tone: "warning" },
  { label: "Scan quality", value: "94%", tone: "verified" },
] as const;

export default function DashboardPage({ detections, analysisResult, onViewSonar, onSelectDetection }: Props) {
  const metrics = analysisResult ? [
    { label: "Scans analyzed", value: "01", tone: "default" as const },
    { label: "Detections", value: String(analysisResult.detections.length).padStart(2, "0"), tone: "default" as const },
    { label: "High priority", value: String(detections.filter((detection) => detection.priority === "high").length).padStart(2, "0"), tone: "warning" as const },
    { label: "Scan quality", value: "N/A", tone: "default" as const },
  ] : demoMetrics;
  const columns: ReadonlyArray<Column<Detection>> = [
    { key: "id", label: "ID", render: (row) => `#${row.id}` },
    { key: "type", label: "Object", render: (row) => row.type },
    { key: "sourceDataset", label: "Dataset", render: (row) => row.sourceDataset ?? "DEMO" },
    { key: "confidence", label: "Confidence", render: (row) => row.confidence === null ? "—" : `${row.confidence}%` },
    { key: "priority", label: "Priority", render: (row) => <span className={`priority-pill priority-${row.priority}`}>{row.priority}</span> },
  ];
  return <>
    <SonarDashboardIntro title="Marine Debris Intelligence" description="AI-powered analysis of underwater side-scan sonar imagery." metrics={metrics} actionLabel="Open sonar analysis" dataStatus={analysisResult?.mode ?? "DEMO DATA"} />
    <section className="dashboard-lower page-section"><div className="section-heading"><div><span className="eyebrow">{analysisResult ? `UPLOAD · ${analysisResult.mode}` : "FIELD ACTIVITY · DEMO DATA"}</span><h2>Recent detections</h2></div>{analysisResult && <a className="text-action" href="#detections">View all detections ↓</a>}</div>
      <div className="dashboard-grid"><div className="panel recent-panel"><DataTable rows={(analysisResult ? detections : demoDetections).slice(0, 5)} columns={columns} label="Recent marine debris detections" onSelect={analysisResult ? (row) => { onSelectDetection(row.id); onViewSonar(); } : undefined} /></div><div className="panel next-step-panel"><span className="eyebrow">NEXT STEP</span><h3>Review sonar evidence</h3><p>{analysisResult ? "Inspect detections returned for the uploaded image." : "Upload a sonar image to run it through the analysis API and reveal the scan results."}</p><button className="primary-button" onClick={onViewSonar}>{analysisResult ? "Open sonar analysis" : "Upload a sonar scan"} <span>↓</span></button>{analysisResult && <a className="secondary-button" href="#detection-map">Explore detection map</a>}</div></div>
    </section>
  </>;
}
