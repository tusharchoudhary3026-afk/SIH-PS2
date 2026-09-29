import type { AnalysisPreferences, Detection } from "../state/app-types";
import type { AnalysisDetection } from "../services/engine8-api";

type Props = {
  detections: ReadonlyArray<Detection>;
  selectedDetectionId: number | null;
  onSelectDetection: (id: number) => void;
  preferences: AnalysisPreferences;
  imageUrl: string | null;
  imageLabel?: string;
  onImageError: () => void;
  zoom: number;
  compare: boolean;
  apiDetections?: ReadonlyArray<AnalysisDetection> | null;
  apiImageSize?: { width: number; height: number } | null;
  showApiDetections?: boolean;
  onSelectApiDetection?: (id: string) => void;
};

const markerPositions = [[20, 38], [47, 63], [70, 30], [81, 70], [34, 76], [61, 48]] as const;

export default function SonarViewer({ detections, selectedDetectionId, onSelectDetection, preferences, imageUrl, imageLabel, onImageError, zoom, compare, apiDetections = null, apiImageSize = null, showApiDetections = true, onSelectApiDetection }: Props) {
  return <div className={`sonar-viewer${compare ? " is-comparing" : ""}`}>
    <div className="viewer-toolbar"><span><i /> SIDE-SCAN SONAR · {imageLabel ?? "DEMO SURVEY"} <small>{imageUrl ? "UPLOADED IMAGE" : "DEMO IMAGE"}</small></span><span>{zoom}% <small>ZOOM</small></span></div>
    <div className="sonar-canvas" style={{ "--sonar-zoom": zoom / 100 } as React.CSSProperties}>
      {imageUrl ? <img className="uploaded-sonar" src={imageUrl} alt="Locally selected sonar image preview" onError={onImageError} /> : <svg className="sonar-art" viewBox="0 0 1200 600" role="img" aria-label="Illustrative side-scan sonar image with seafloor texture"><defs><linearGradient id="seafloor" x2="0" y2="1"><stop stopColor="#24606b"/><stop offset=".48" stopColor="#152e3a"/><stop offset="1" stopColor="#091922"/></linearGradient><pattern id="grain" width="33" height="27" patternUnits="userSpaceOnUse"><circle cx="4" cy="6" r="1.3" fill="#a6ebe0" opacity=".5"/><circle cx="21" cy="14" r="2" fill="#e9c285" opacity=".45"/><circle cx="28" cy="4" r=".8" fill="#c0e2df" opacity=".7"/><path d="M8 20l6-1M25 24l4-2" stroke="#8bcac7" opacity=".34"/></pattern><linearGradient id="shadow" x2="1"><stop stopColor="#06131c" stopOpacity=".08"/><stop offset=".4" stopColor="#030a0d" stopOpacity=".95"/><stop offset="1" stopColor="#06131c" stopOpacity=".05"/></linearGradient></defs><rect width="1200" height="600" fill="#07131a"/><path d="M0 80Q280 20 610 87T1200 52V520Q870 570 570 510T0 560Z" fill="url(#seafloor)"/><path d="M0 80Q280 20 610 87T1200 52V520Q870 570 570 510T0 560Z" fill="url(#grain)"/><path d="M180 326q86-95 220-68t190 58q-118 6-201 48t-209-38" fill="#c4dfcf" opacity=".65"/><path d="M405 304q105-52 243 6l130 57q-123-25-228 17-75 29-145-80" fill="url(#shadow)"/><path d="M800 140q70 20 121 72t142 22M90 430q110-34 192-6t151 20" fill="none" stroke="#d9c491" strokeWidth="4" opacity=".38"/><path d="M0 300h1200M0 304h1200" stroke="#5be1d3" opacity=".16"/></svg>}
      <div className="scan-grid" aria-hidden="true" />
      {preferences.showAcousticShadows && !imageUrl && <div className="shadow-highlight" aria-hidden="true" />}
      {compare && <div className="compare-split" aria-hidden="true"><span>JAN 2026 · BASELINE</span><span>JUN 2026 · CURRENT</span></div>}
      {showApiDetections && preferences.showDetections && imageUrl && apiDetections && apiImageSize && apiDetections.map((detection) => {
        const [x1, y1, x2, y2] = detection.bbox;
        return <button key={detection.detection_id} className="api-detection-box" style={{ left: `${100*x1/apiImageSize.width}%`, top: `${100*y1/apiImageSize.height}%`, width: `${100*(x2-x1)/apiImageSize.width}%`, height: `${100*(y2-y1)/apiImageSize.height}%` }} aria-label={`${detection.class_name} from ${detection.source_dataset}, raw score ${detection.raw_confidence.toFixed(3)}`} onClick={() => onSelectApiDetection?.(detection.detection_id)}><span>{detection.class_name} · {detection.source_dataset}</span></button>;
      })}
      {preferences.showDetections && !imageUrl && detections.slice(0, markerPositions.length).map((detection, index) => {
        const [left, top] = markerPositions[index];
        if (detection.confidence !== null && detection.confidence < preferences.confidenceThreshold) return null;
        return <button key={detection.id} className={`sonar-marker priority-${detection.priority}${selectedDetectionId === detection.id ? " is-selected" : ""}`} style={{ left: `${left}%`, top: `${top}%` }} aria-label={`Detection ${detection.id}, ${detection.type}, ${detection.confidence ?? "unknown"}% confidence`} onClick={() => onSelectDetection(detection.id)}><span>{detection.id}</span></button>;
      })}
      <span className="viewer-scale">0 ━━━━━━━━ 10 m</span>
    </div>
    <div className="viewer-foot"><span>{imageUrl ? "Uploaded sonar return" : "Illustrative seabed return"}</span><span>Selected target <b>#{selectedDetectionId ?? "—"}</b></span></div>
  </div>;
}
