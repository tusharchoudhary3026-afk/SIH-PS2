import MetricCard from "../components/metric-card";
import type { Detection } from "../state/app-types";
import type { AnalysisResult } from "../services/engine8-api";

type Props = { detections: ReadonlyArray<Detection>; analysisResult: AnalysisResult };

export default function AnalyticsPage({ detections, analysisResult }: Props) {
  const classes = [...new Set(detections.map((item) => item.type))].sort();
  const priorities = ["high", "medium", "low", "uncertain"] as const;
  const classCounts = classes.map((type) => ({ type, count: detections.filter((item) => item.type === type).length }));
  const highPriorityCount = detections.filter((item) => item.priority === "high").length;
  const datasetCounts = [...new Set(analysisResult.detections.map((item) => item.source_dataset))].map((dataset) => ({ dataset, count: analysisResult.detections.filter((item) => item.source_dataset === dataset).length }));
  return <div className="page-section">
    <div className="page-intro"><div><span className="eyebrow">SCAN INSIGHTS · {analysisResult.mode}</span><h2>Analytics</h2><p>Counts and classifications returned for {analysisResult.filename}.</p></div><span className="live-indicator">{detections.length} DETECTIONS</span></div>
    <div className="analytics-metrics"><MetricCard label="Scans analyzed" value="01" /><MetricCard label="Object detections" value={String(detections.length).padStart(2, "0")} tone="warning" /><MetricCard label="Scan quality" value="N/A" /><MetricCard label="High priority" value={String(highPriorityCount).padStart(2, "0")} tone="warning" /></div>
    <div className="analytics-grid"><section className="panel chart-panel"><div className="section-heading"><div><span className="eyebrow">OBJECT CLASSES</span><h3>Classification breakdown</h3></div></div>{classCounts.length ? classCounts.map(({ type, count }) => <div className="bar-row" key={type}><span>{type}</span><div><i style={{ width: `${(count / detections.length) * 100}%` }} /></div><strong>{count}</strong></div>) : <p className="muted">No classes were returned for this image.</p>}</section><section className="panel chart-panel"><div className="section-heading"><div><span className="eyebrow">RESPONSE LEVELS</span><h3>Inspection priority</h3></div></div>{priorities.map((priority) => { const count = detections.filter((item) => item.priority === priority).length; return <div className="priority-stat" key={priority}><span className={`priority-pill priority-${priority}`}><i />{priority}</span><strong>{String(count).padStart(2, "0")}</strong><small>{detections.length ? `${Math.round((count / detections.length) * 100)}%` : "—"}</small></div>; })}</section></div>
    <section className="panel quality-panel"><div className="section-heading"><div><span className="eyebrow">SCAN QUALITY</span><h3>Not returned by this analysis API</h3></div><span className="quality-ring quality-ring-unavailable">N/A</span></div><p className="muted">Quality metrics are not present in the image-analysis response, so no sample quality score is shown for this scan.</p><div className="quality-table"><div><strong>Available output</strong><strong>Value</strong></div><div><span>Image dimensions</span><span>{analysisResult.image_width} × {analysisResult.image_height}px</span></div><div><span>Detector status</span><span>{analysisResult.detector_status}</span></div>{datasetCounts.map(({ dataset, count }) => <div key={dataset}><span>{dataset}</span><span>{count} detections</span></div>)}</div></section>
  </div>;
}
