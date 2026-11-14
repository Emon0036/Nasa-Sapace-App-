import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Satellite } from "lucide-react";
import { AIRecommendations } from "./pages/AIRecommendations";
import { MissionSimulator } from "./pages/MissionSimulator";
import { Overview } from "./pages/Overview";
import { ScenarioComparison } from "./pages/ScenarioComparison";
import { SeasonalSweep } from "./pages/SeasonalSweep";
import { SiteAnalysis } from "./pages/SiteAnalysis";
import { Layout, type PageKey } from "./components/Layout";
import { MissionControls, type CustomSiteInput } from "./components/MissionControls";
import { getHealth, getModelMetrics, getScienceStatus, getSites, getTerrainRegions, analyzeSite } from "./services/api";
import type { AnalysisResult, ModelMetrics, ScienceStatus, Site, TerrainRegion } from "./types";

function localDateTime(value: Date) {
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

function localToUtc(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "" : parsed.toISOString();
}

export default function App() {
  const [page, setPage] = useState<PageKey>("overview");
  const [sites, setSites] = useState<Site[]>([]);
  const [terrainRegions, setTerrainRegions] = useState<TerrainRegion[]>([]);
  const [selectedSiteIds, setSelectedSiteIds] = useState<string[]>([]);
  const [startLocal, setStartLocal] = useState(() => localDateTime(new Date(Date.now() + 24 * 60 * 60 * 1000)));
  const [durationDays, setDurationDays] = useState(5);
  const [stepMinutes, setStepMinutes] = useState(15);
  const [includeTerrain, setIncludeTerrain] = useState(true);
  const [results, setResults] = useState<Record<string, AnalysisResult>>({});
  const [focusedSiteId, setFocusedSiteId] = useState("");
  const [siteErrors, setSiteErrors] = useState<Record<string, string>>({});
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const [backendName, setBackendName] = useState<string>();
  const [scienceStatus, setScienceStatus] = useState<ScienceStatus | null>(null);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [metricsLoaded, setMetricsLoaded] = useState(false);
  const [pageError, setPageError] = useState("");
  const analysisController = useRef<AbortController | null>(null);
  const defaultsApplied = useRef(false);

  useEffect(() => {
    let active = true;
    void getHealth().then((health) => {
      if (!active) return;
      setBackendOnline(health.status === "ok");
      setBackendName(health.ephemeris_backend);
    }).catch(() => { if (active) setBackendOnline(false); });
    void getSites().then((catalog) => {
      if (!active) return;
      setSites(catalog);
      setPageError("");
      if (!defaultsApplied.current) {
        setSelectedSiteIds(catalog.filter((site) => site.region === "south_polar" && site.site_id !== "cabeus").map((site) => site.site_id));
        defaultsApplied.current = true;
      }
    }).catch((error: unknown) => {
      if (active) setPageError(error instanceof Error ? error.message : "Could not load candidate sites.");
    });
    void getTerrainRegions().then((regions) => { if (active) setTerrainRegions(regions); }).catch(() => undefined);
    void getScienceStatus().then((status) => {
      if (!active) return;
      setScienceStatus(status);
      setBackendName(status.ephemeris_backend);
    }).catch(() => undefined);
    return () => {
      active = false;
      analysisController.current?.abort();
    };
  }, [connectionAttempt]);

  useEffect(() => {
    if (page !== "recommendations" || metricsLoaded) return;
    const controller = new AbortController();
    void getModelMetrics(controller.signal).then((response) => {
      if (controller.signal.aborted) return;
      setMetrics(response.metrics);
      setMetricsLoaded(true);
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      setPageError(error instanceof Error ? error.message : "Could not load saved model metrics.");
      setMetricsLoaded(true);
    });
    return () => controller.abort();
  }, [page, metricsLoaded]);

  const runAnalysis = async (customSite: CustomSiteInput | null) => {
    const startUtc = localToUtc(startLocal);
    const siteIds = [...selectedSiteIds];
    if (customSite) siteIds.push(customSite.site_id);
    if (!startUtc || !siteIds.length) {
      setPageError(!startUtc ? "Choose a valid mission start." : "Select at least one site.");
      return;
    }
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    setAnalysisLoading(true);
    setPageError("");
    setSiteErrors({});
    setResults({});
    const resultBySite: Record<string, AnalysisResult> = {};
    const errorsBySite: Record<string, string> = {};
    const inputFor = (siteId: string) => ({
      site_id: siteId,
      start_utc: startUtc,
      duration_hours: durationDays * 24,
      step_minutes: stepMinutes,
      include_terrain: includeTerrain,
      ...(customSite && siteId === customSite.site_id ? {
        site_name: customSite.site_name,
        lat_deg: customSite.lat_deg,
        lon_deg: customSite.lon_deg,
        elev_m: customSite.elev_m,
      } : {}),
    });
    let cursor = 0;
    const worker = async () => {
      while (cursor < siteIds.length && !controller.signal.aborted) {
        const index = cursor;
        cursor += 1;
        const siteId = siteIds[index];
        try {
          resultBySite[siteId] = await analyzeSite(inputFor(siteId), controller.signal);
        } catch (error) {
          if (controller.signal.aborted) return;
          errorsBySite[siteId] = error instanceof Error ? error.message : "Analysis failed.";
        }
      }
    };
    await Promise.all(Array.from({ length: Math.min(2, siteIds.length) }, () => worker()));
    if (controller.signal.aborted) return;
    setResults(resultBySite);
    setSiteErrors(errorsBySite);
    setFocusedSiteId(Object.keys(resultBySite)[0] ?? "");
    setBackendOnline(Object.keys(resultBySite).length > 0);
    if (!Object.keys(resultBySite).length) setPageError("No site returned an analysis. Check the backend message below and retry.");
    setAnalysisLoading(false);
  };

  const focusSiteId = focusedSiteId && results[focusedSiteId]
    ? focusedSiteId
    : results[selectedSiteIds[0]] ? selectedSiteIds[0] : Object.keys(results)[0] ?? "";
  const builtinSelectedSiteIds = selectedSiteIds.filter((id) => sites.some((site) => site.site_id === id));
  const startUtc = localToUtc(startLocal);
  const content = (() => {
    switch (page) {
      case "overview": return <Overview sites={sites} results={results} loading={analysisLoading} errors={siteErrors} onPageChange={setPage} onSelectSite={setFocusedSiteId} />;
      case "site": return <SiteAnalysis results={results} selectedSiteId={focusSiteId} onSelectSite={setFocusedSiteId} />;
      case "seasonal": return <SeasonalSweep sites={sites} selectedSiteIds={builtinSelectedSiteIds} startUtc={startUtc} durationHours={durationDays * 24} stepMinutes={stepMinutes} includeTerrain={includeTerrain} />;
      case "compare": return <ScenarioComparison sites={sites} selectedSiteIds={builtinSelectedSiteIds} startLocal={startLocal} durationHours={durationDays * 24} stepMinutes={stepMinutes} includeTerrain={includeTerrain} />;
      case "simulator": return <MissionSimulator sites={sites} selectedSiteIds={builtinSelectedSiteIds} startUtc={startUtc} defaultStep={stepMinutes} />;
      case "recommendations": return <AIRecommendations sites={sites} selectedSiteIds={builtinSelectedSiteIds} startUtc={startUtc} durationHours={durationDays * 24} stepMinutes={stepMinutes} includeTerrain={includeTerrain} modelAvailable={scienceStatus?.ml_model_available ?? false} metrics={metrics} />;
      default: return null;
    }
  })();

  return <Layout page={page} onPageChange={(next) => { setPage(next); setPageError(""); }} backendOnline={backendOnline} backendName={backendName}>
    <div className="page-shell">
      {page !== "simulator" && <MissionControls sites={sites} terrainRegions={terrainRegions} selectedSiteIds={selectedSiteIds} onSelectedSitesChange={setSelectedSiteIds} startLocal={startLocal} onStartLocalChange={setStartLocal} durationDays={durationDays} onDurationDaysChange={setDurationDays} stepMinutes={stepMinutes} onStepMinutesChange={setStepMinutes} includeTerrain={includeTerrain} onIncludeTerrainChange={setIncludeTerrain} loading={analysisLoading} onRun={(customSite) => { void runAnalysis(customSite); }} />}
      {!backendOnline && <div className="notice notice-error connection-notice"><AlertTriangle size={16} /><span>Cannot reach the FastAPI service. Start the backend at <code>http://localhost:8000</code>, then retry.</span><button className="button button-secondary button-small" onClick={() => { setPageError(""); setBackendOnline(null); setConnectionAttempt((attempt) => attempt + 1); }}>Retry connection</button><Satellite size={15} /></div>}
      {pageError && <div className="notice notice-error connection-notice"><AlertTriangle size={16} /><span>{pageError}</span></div>}
      {content}
      <footer className="app-footer"><span>LUNAR HORIZON · RESEARCH / EDUCATION PROTOTYPE</span><span>NOT FLIGHT-CERTIFIED · VALUES ARE SCIENTIFIC ESTIMATES</span></footer>
    </div>
  </Layout>;
}
