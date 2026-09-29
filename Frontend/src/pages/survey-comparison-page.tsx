import type { Detection } from "../state/app-types";
import type { AnalysisResult } from "../services/engine8-api";

type Props = { view?: "comparison" | "returned"; detections: ReadonlyArray<Detection>; analysisResult: AnalysisResult; onSelectDetection: (id: number) => void; onViewSonar: () => void };

export default function SurveyComparisonPage({ view = "comparison", detections, analysisResult, onSelectDetection, onViewSonar }: Props) {
  const comparisonView = view === "comparison";
  return <div className="page-section">
    <div className="page-intro"><div><span className="eyebrow">{comparisonView ? "TEMPORAL MONITORING · UPLOADED SCAN" : "CURRENT SCAN · UPLOADED IMAGE"}</span><h2>{comparisonView ? "Survey comparison" : "Returned detections"}</h2><p>{comparisonView ? "Compare repeat survey coverage to track newly appeared or persistent objects." : "Review the objects returned for this image."}</p></div>{comparisonView && <span className="live-indicator">BASELINE REQUIRED</span>}</div>
    {comparisonView && <section className="panel comparison-empty-state"><span className="eyebrow">{analysisResult.filename}</span><h3>A second survey is needed for temporal comparison</h3><p>This scan has {detections.length} returned detections. New, removed, and persistent counts need an earlier survey of the same area, so no comparison values are inferred.</p><div className="comparison-next-step"><span>Current scan</span><strong>{analysisResult.image_id}</strong><span>Baseline scan</span><strong>Not supplied</strong></div></section>}
    {detections.length > 0 ? <section className="changed-list"><div className="section-heading">{comparisonView && <div><span className="eyebrow">CURRENT SCAN</span><h2>Returned detections</h2></div>}<button className="text-action" onClick={onViewSonar}>Open sonar review ↓</button></div><div className="changed-chips">{detections.map((detection) => <button key={detection.id} onClick={() => { onSelectDetection(detection.id); onViewSonar(); }}><span className={`priority-pill priority-${detection.priority}`}>#{String(detection.id).padStart(2, "0")}</span><strong>{detection.type}</strong><small>{detection.sourceDataset ?? "dataset unavailable"} · {detection.confidence === null ? "un-calibrated" : `${detection.confidence}%`}</small><span aria-hidden="true">↗</span></button>)}</div></section> : <p className="muted">No detections were returned for this image.</p>}
  </div>;
}
