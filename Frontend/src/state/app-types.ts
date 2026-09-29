export type PageId =
  | "dashboard"
  | "sonar-analysis"
  | "detections"
  | "detection-map"
  | "survey-comparison"
  | "analytics"
  | "reports"
  | "settings";

export type AnalysisPreferences = {
  showDetections: boolean;
  showAcousticShadows: boolean;
  confidenceThreshold: number;
};

export type Survey = {
  id: string;
  label: string;
  date: string;
};

export type QualitySummary = {
  overall: number;
  speckleNoise: "good" | "moderate" | "poor";
  dataGaps: "low" | "moderate" | "high";
  motionDistortion: "good" | "moderate" | "poor";
  coverage: "good" | "moderate" | "poor";
};

export type Detection = {
  id: number;
  type: string;
  confidence: number | null;
  estimatedSizeM: number | null;
  latitude: string;
  longitude: string;
  priority: "high" | "medium" | "low" | "uncertain";
  status: "review" | "verified" | "natural" | "needs-verification" | "rejected";
  evidence: ReadonlyArray<{ label: string; description: string }>;
  recommendedAction: string;
  surveyId: string;
  change: "new" | "removed" | "persistent" | null;
  apiId?: string;
  sourceDataset?: string;
  bbox?: [number, number, number, number];
  geolocationType?: "Real" | "Simulated" | "Unavailable";
  latitudeValue?: number | null;
  longitudeValue?: number | null;
};
