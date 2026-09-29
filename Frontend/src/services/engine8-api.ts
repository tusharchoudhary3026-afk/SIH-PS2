export type GeolocationType = "Real" | "Simulated" | "Unavailable";

export type AnalysisDetection = {
  detection_id: string;
  image_id: string;
  class_id: number;
  class_name: string;
  bbox: [number, number, number, number];
  raw_confidence: number;
  shadow_consistency: number | null;
  local_contrast: number | null;
  aspect_ratio: number;
  normalized_area: number;
  fusion_score: number | null;
  calibrated_confidence: number | null;
  confidence_status: string;
  false_positive_status: "keep" | "review" | "reject";
  reason_codes: string[];
  source_dataset: string;
  provenance: Record<string, unknown>;
  latitude: number | null;
  longitude: number | null;
  geolocation_type: GeolocationType;
  geolocation_status: string;
  metadata_source: string | null;
  inspection_priority: { label: string; score: number | null; band: string; fields_used: string[]; note: string };
  human_review: { status: string; note?: string; updated_at?: string };
  shadow_diagnostics: Record<string, unknown>;
  contrast_diagnostics: Record<string, unknown>;
};

export type AnalysisResult = {
  mode: "MOCK" | "REAL" | "UNAVAILABLE";
  image_id: string;
  filename: string;
  image_width: number;
  image_height: number;
  source_dataset: string;
  datasets?: string[];
  detector_status: string;
  message: string | null;
  detections: AnalysisDetection[];
  location_policy: string;
};

export type ApiHealth = { status: string; mode: "MOCK" | "REAL" | "UNAVAILABLE"; engine4: string; subpipe: string };

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function decode<T>(response: Response): Promise<T> {
  const body = await response.json() as T & { error?: string };
  if (!response.ok) throw new Error(body.error ?? `API request failed (${response.status})`);
  return body;
}

export async function getApiHealth(): Promise<ApiHealth> {
  return decode<ApiHealth>(await fetch(`${apiBase}/api/health`));
}

export async function analyzeImage(file: File): Promise<AnalysisResult> {
  return decode<AnalysisResult>(await fetch(`${apiBase}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": file.name, "X-Source-Dataset": "ALL" },
    body: file,
  }));
}

export async function saveReview(detectionId: string, action: "confirm" | "reject" | "flag", note = "") {
  return decode<{ detection_id: string; human_review: { status: string; note: string; updated_at: string } }>(await fetch(`${apiBase}/api/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ detection_id: detectionId, action, note }),
  }));
}

export function exportAnalysis(result: AnalysisResult, format: "json" | "csv"): void {
  const headers = ["detection_id", "image_id", "class_name", "bbox", "raw_confidence", "calibrated_confidence", "confidence_status", "shadow_consistency", "local_contrast", "geolocation_type", "latitude", "longitude", "source_dataset", "provenance", "human_review"];
  const csv = [headers, ...result.detections.map((detection) => headers.map((key) => detection[key as keyof AnalysisDetection]))]
    .map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\r\n");
  const content = format === "json" ? JSON.stringify(result, null, 2) : csv;
  const url = URL.createObjectURL(new Blob([content], { type: format === "json" ? "application/json" : "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `sonar-analysis-${result.image_id}.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}
