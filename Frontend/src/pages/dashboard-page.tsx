import SonarDashboardIntro from "../components/sonar-dashboard-intro";
import type { AnalysisResult } from "../services/engine8-api";

type Props = { analysisResult: AnalysisResult | null };

const demoMetrics = [
  { label: "Target classes", value: "04", tone: "default" },
  { label: "Evidence cues", value: "03", tone: "default" },
  { label: "Location", value: "Verified only", tone: "default" },
  { label: "Review", value: "Human-led", tone: "default" },
] as const;

export default function DashboardPage({ analysisResult }: Props) {
  const metrics = analysisResult ? [
    { label: "Scans analyzed", value: "01", tone: "default" as const },
    { label: "Detections", value: String(analysisResult.detections.length).padStart(2, "0"), tone: "default" as const },
    { label: "High priority", value: String(analysisResult.detections.filter((row) => row.inspection_priority.band === "high").length).padStart(2, "0"), tone: "warning" as const },
    { label: "Scan quality", value: "N/A", tone: "default" as const },
  ] : demoMetrics;

  return <SonarDashboardIntro
    title="Underwater debris detection"
    description="SEVORA is designed to use AI on side-scan sonar imagery to surface candidate debris and seabed anomalies for human review."
    metrics={metrics}
    dataStatus={analysisResult?.mode === "MOCK" ? "MOCK DATA" : analysisResult?.mode ?? "DEMO DATA"}
  />;
}
