import { useState } from "react";
import SectionNav from "./components/section-nav";
import DashboardPage from "./pages/dashboard-page";
import SonarAnalysisPage, { type AnalysisResultTab } from "./pages/sonar-analysis-page";
import DetectionsPage from "./pages/detections-page";
import DetectionMapPage from "./pages/detection-map-page";
import SurveyComparisonPage from "./pages/survey-comparison-page";
import AnalyticsPage from "./pages/analytics-page";
import ReportsPage from "./pages/reports-page";
import SettingsPage from "./pages/settings-page";
import type { AnalysisPreferences } from "./state/app-types";
import { demoDetections } from "./state/demo-data";
import { mapAnalysisDetections } from "./services/map-analysis-result";
import type { AnalysisResult } from "./services/engine8-api";

const defaultPreferences: AnalysisPreferences = { showDetections: true, showAcousticShadows: true, confidenceThreshold: 50 };
const storageKey = "marine-debris-intelligence.preferences.v1";

function loadPreferences(): { value: AnalysisPreferences; message: string } {
  try {
    const stored = window.localStorage.getItem(storageKey);
    if (!stored) return { value: defaultPreferences, message: "" };
    const parsed = JSON.parse(stored) as Partial<AnalysisPreferences>;
    if (typeof parsed.showDetections !== "boolean" || typeof parsed.showAcousticShadows !== "boolean" || typeof parsed.confidenceThreshold !== "number" || !Number.isFinite(parsed.confidenceThreshold) || parsed.confidenceThreshold < 0 || parsed.confidenceThreshold > 100) {
      return { value: defaultPreferences, message: "Saved preferences were invalid; using browser defaults." };
    }
    return { value: { showDetections: parsed.showDetections, showAcousticShadows: parsed.showAcousticShadows, confidenceThreshold: parsed.confidenceThreshold }, message: "" };
  } catch {
    return { value: defaultPreferences, message: "Browser storage is unavailable; preferences will last for this session." };
  }
}

export default function App() {
  const [selectedDetectionId, setSelectedDetectionId] = useState<number | null>(17);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [activeResultTab, setActiveResultTab] = useState<AnalysisResultTab>("engine-results");
  const [loadedPreferences] = useState(loadPreferences);
  const [preferences, setPreferences] = useState<AnalysisPreferences>(loadedPreferences.value);
  const [storageMessage, setStorageMessage] = useState(loadedPreferences.message);

  const detections = analysisResult ? mapAnalysisDetections(analysisResult.detections) : demoDetections;
  const selectDetection = (id: number) => {
    if (detections.some((detection) => detection.id === id)) setSelectedDetectionId(id);
  };
  const receiveAnalysis = (result: AnalysisResult | null) => {
    setAnalysisResult(result);
    setSelectedDetectionId(result?.detections.length ? 1 : null);
    if (result) setActiveResultTab("engine-results");
  };
  const viewSonar = () => document.getElementById("sonar-analysis")?.scrollIntoView({ behavior: "smooth", block: "start" });
  const changeResultTab = (tab: AnalysisResultTab) => {
    setActiveResultTab(tab);
    window.setTimeout(() => document.getElementById("active-result-view")?.scrollIntoView({ behavior: "smooth", block: "start" }), 40);
  };
  const changePreferences = (next: AnalysisPreferences) => {
    setPreferences(next);
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(next));
      setStorageMessage("");
    } catch {
      setStorageMessage("Browser storage is unavailable; preferences will last for this session.");
    }
  };

  return <main className="page-content scroll-page">
    <SectionNav analysisAvailable={false} />
    <section id="dashboard" className="scroll-section scroll-section-hero"><DashboardPage analysisResult={analysisResult} /></section>
    <section id="sonar-analysis" className="scroll-section"><SonarAnalysisPage detections={detections} selectedDetectionId={selectedDetectionId} onSelectDetection={selectDetection} preferences={preferences} onPreferencesChange={changePreferences} analysisResult={analysisResult} onAnalysisResult={receiveAnalysis} activeResultTab={activeResultTab} onResultTabChange={changeResultTab} />
    {analysisResult && activeResultTab !== "engine-results" && activeResultTab !== "detection-evidence" && <div id="active-result-view" className="result-view-section">
      {activeResultTab === "detection-register" && <DetectionsPage detections={detections} selectedDetectionId={selectedDetectionId} onSelectDetection={(id) => { selectDetection(id); viewSonar(); }} />}
      {activeResultTab === "coordinate-plot" && <DetectionMapPage detections={detections} selectedDetectionId={selectedDetectionId} onSelectDetection={selectDetection} onViewSonar={viewSonar} />}
      {activeResultTab === "survey-comparison" && <SurveyComparisonPage view="comparison" detections={detections} analysisResult={analysisResult} onSelectDetection={selectDetection} onViewSonar={viewSonar} />}
      {activeResultTab === "returned-detections" && <SurveyComparisonPage view="returned" detections={detections} analysisResult={analysisResult} onSelectDetection={selectDetection} onViewSonar={viewSonar} />}
      {activeResultTab === "analytics" && <AnalyticsPage detections={detections} analysisResult={analysisResult} />}
      {activeResultTab === "reports" && <ReportsPage detections={detections} analysisResult={analysisResult} />}
      {activeResultTab === "settings" && <SettingsPage preferences={preferences} onChange={changePreferences} storageMessage={storageMessage} />}
    </div>}
    </section>
  </main>;
}
