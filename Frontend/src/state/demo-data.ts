import type { Detection, QualitySummary, Survey } from "./app-types";

export const demoSurveys: ReadonlyArray<Survey> = [
  { id: "survey-jan-2026", label: "January 2026", date: "2026-01-18" },
  { id: "survey-jun-2026", label: "June 2026", date: "2026-06-22" },
];

export const demoQuality: QualitySummary = {
  overall: 94,
  speckleNoise: "good",
  dataGaps: "low",
  motionDistortion: "moderate",
  coverage: "good",
};

const types = ["Ghost Net (experimental)", "Pipe", "Rock", "Shipwreck", "Coral", "Mine-like Contact", "Sand Ripple", "Crab Pot"];
const highIds = new Set([17, 18, 20, 22, 24, 26, 28, 30]);
const changes = new Map<number, Detection["change"]>([
  [17, "new"], [18, "new"], [20, "new"], [22, "new"],
  [24, "removed"], [26, "removed"],
  [28, "persistent"], [30, "persistent"], [32, "persistent"], [34, "persistent"],
  [36, "persistent"], [38, "persistent"], [40, "persistent"],
]);

function createDetection(id: number): Detection {
  const type = id === 17 ? "Ghost Net (experimental)" : types[(id - 1) % types.length];
  const priority: Detection["priority"] = highIds.has(id)
    ? "high"
    : id % 4 === 0 ? "medium" : id % 5 === 0 ? "uncertain" : "low";
  const evidence = id === 17
    ? [
        { label: "Linear structure", description: "Irregular linear pattern across the seafloor." },
        { label: "Acoustic shadow", description: "A distinct shadow follows the detected return." },
        { label: "Texture inconsistency", description: "The return differs from the surrounding seabed." },
      ]
    : [
        { label: "Shape", description: "Pattern differs from nearby seabed texture." },
        { label: "Acoustic return", description: "Return strength is consistent with this demo class." },
      ];

  return {
    id,
    type,
    confidence: id === 19 ? null : id === 17 ? 91 : 72 + ((id * 7) % 24),
    estimatedSizeM: id === 19 ? null : id === 17 ? 8.4 : Number((2.5 + ((id * 13) % 90) / 10).toFixed(1)),
    latitude: `SIMULATED · 18.${String(4200 + id * 17).padStart(5, "0")}° N`,
    longitude: `SIMULATED · 72.${String(8100 + id * 13).padStart(5, "0")}° E`,
    geolocationType: "Simulated",
    latitudeValue: 18.42 + id * 0.0017,
    longitudeValue: 72.81 + id * 0.0013,
    priority,
    status: type === "Rock" || type === "Coral" || type === "Sand Ripple"
      ? "natural"
      : id === 17 ? "needs-verification" : id % 6 === 0 ? "verified" : "review",
    evidence,
    recommendedAction: id === 17 ? "Verify with secondary survey / ROV" : "Review against the original sonar scan",
    surveyId: id % 2 === 0 ? "survey-jun-2026" : "survey-jan-2026",
    change: changes.get(id) ?? null,
  };
}

export const demoDetections: ReadonlyArray<Detection> = Array.from({ length: 37 }, (_, index) =>
  createDetection(index + 14),
);

export function findDetection(id: number): Detection | undefined {
  return demoDetections.find((detection) => detection.id === id);
}

export function getDetectionsForSurvey(surveyId: string): ReadonlyArray<Detection> {
  return demoDetections.filter((detection) => detection.surveyId === surveyId);
}
