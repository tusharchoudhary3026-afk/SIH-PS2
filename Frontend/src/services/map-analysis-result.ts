import type { Detection } from "../state/app-types";
import type { AnalysisDetection } from "./engine8-api";

function priorityFromBand(band: string): Detection["priority"] {
  const normalized = band.toLowerCase();
  if (normalized.includes("high") || normalized.includes("critical")) return "high";
  if (normalized.includes("medium") || normalized.includes("moderate")) return "medium";
  if (normalized.includes("low")) return "low";
  return "uncertain";
}

function coordinate(value: number | null, positive: string, negative: string): string {
  if (value === null || !Number.isFinite(value)) return "Unavailable";
  return `${Math.abs(value).toFixed(5)}° ${value >= 0 ? positive : negative}`;
}

export function mapAnalysisDetections(rows: ReadonlyArray<AnalysisDetection>): ReadonlyArray<Detection> {
  return rows.map((row, index) => {
    const reviewStatus = row.human_review.status.toLowerCase();
    const status: Detection["status"] = reviewStatus === "confirm" || reviewStatus === "confirmed"
      ? "verified"
      : reviewStatus === "reject" || reviewStatus === "rejected"
        ? "rejected"
        : reviewStatus === "flag" || reviewStatus === "flagged"
          ? "needs-verification"
          : row.false_positive_status === "reject" ? "rejected" : "review";
    const evidence = [
      { label: "Detection rationale", description: row.reason_codes.length ? row.reason_codes.join(", ") : "The backend did not return rationale codes for this detection." },
      { label: "Acoustic shadow", description: row.shadow_consistency === null ? "Shadow consistency is unavailable." : `Shadow consistency score: ${row.shadow_consistency.toFixed(3)}.` },
      { label: "Local contrast", description: row.local_contrast === null ? "Local contrast is unavailable." : `Local contrast score: ${row.local_contrast.toFixed(3)}.` },
    ];

    return {
      id: index + 1,
      apiId: row.detection_id,
      sourceDataset: row.source_dataset,
      bbox: row.bbox,
      geolocationType: row.geolocation_type,
      latitudeValue: row.latitude,
      longitudeValue: row.longitude,
      type: row.class_name,
      confidence: row.calibrated_confidence === null ? null : Math.round(row.calibrated_confidence * 100),
      estimatedSizeM: null,
      latitude: coordinate(row.latitude, "N", "S"),
      longitude: coordinate(row.longitude, "E", "W"),
      priority: priorityFromBand(row.inspection_priority.band),
      status,
      evidence,
      recommendedAction: row.inspection_priority.note || "Review this detector result against the original sonar image.",
      surveyId: row.image_id,
      change: null,
    };
  });
}
