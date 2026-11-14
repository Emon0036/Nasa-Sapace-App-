import { useEffect, useState } from "react";
import { ArrowRightLeft, GitCompareArrows } from "lucide-react";
import type { Data, Layout as PlotLayout } from "plotly.js";
import { compareScenarios, type ScenarioInput } from "../services/api";
import type { ScenarioComparison as ComparisonData, Site } from "../types";
import { EmptyState, MetricCard, SectionTitle, SourceBadge } from "../components/common";
import { ScientificChart } from "../components/ScientificChart";
import { formatUtc, pct } from "../utils/format";

interface ScenarioComparisonProps {
  sites: Site[];
  selectedSiteIds: string[];
  startLocal: string;
  durationHours: number;
  stepMinutes: number;
  includeTerrain: boolean;
}

function localPlusHours(local: string, hours: number) {
  const value = new Date(local);
  value.setHours(value.getHours() + hours);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}T${pad(value.getHours())}:${pad(value.getMinutes())}`;
}

function localToUtc(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("Choose a valid local date and time.");
  return date.toISOString();
}

export function ScenarioComparison({ sites, selectedSiteIds, startLocal, durationHours, stepMinutes, includeTerrain }: ScenarioComparisonProps) {
  const availableSites = sites.filter((site) => selectedSiteIds.includes(site.site_id));
  const firstId = availableSites[0]?.site_id ?? sites[0]?.site_id ?? "";
  const secondId = availableSites[1]?.site_id ?? firstId;
  const [siteA, setSiteA] = useState(firstId);
  const [siteB, setSiteB] = useState(secondId);
  const [timeA, setTimeA] = useState(startLocal);
  const [timeB, setTimeB] = useState(localPlusHours(startLocal, 24));
  const [durationDaysA, setDurationDaysA] = useState(Math.max(1, Math.round(durationHours / 24)));
  const [durationDaysB, setDurationDaysB] = useState(Math.max(1, Math.round(durationHours / 24)));
  const [data, setData] = useState<ComparisonData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const defaultDays = Math.max(1, Math.round(durationHours / 24));
    setDurationDaysA(defaultDays);
    setDurationDaysB(defaultDays);
  }, [durationHours]);

  const run = async () => {
    if (!siteA || !siteB) {
      setError("Choose a site for both scenarios.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const makeInput = (siteId: string, local: string, days: number): ScenarioInput => ({
        site_id: siteId,
        start_utc: localToUtc(local),
        duration_hours: days * 24,
        step_minutes: stepMinutes,
        include_terrain: includeTerrain,
      });
      setData(await compareScenarios(makeInput(siteA, timeA, durationDaysA), makeInput(siteB, timeB, durationDaysB)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Scenario comparison failed.");
    } finally {
      setLoading(false);
    }
  };

  const chartData: Data[] = data ? [
    { type: "scatter", mode: "lines", name: `A · ${data.scenario_a.site.name}`, x: data.scenario_a.time_series.map((row) => row.time_utc), y: data.scenario_a.time_series.map((row) => row.sun_alt_deg), line: { color: "#f5b84b", width: 2 }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Scenario A · %{y:.2f}°<extra></extra>" },
    { type: "scatter", mode: "lines", name: `B · ${data.scenario_b.site.name}`, x: data.scenario_b.time_series.map((row) => row.time_utc), y: data.scenario_b.time_series.map((row) => row.sun_alt_deg), line: { color: "#5ba8ff", width: 2 }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Scenario B · %{y:.2f}°<extra></extra>" },
  ] : [];
  const chartLayout: Partial<PlotLayout> = { yaxis: { title: { text: "Sun altitude (°)" } }, xaxis: { title: { text: "UTC" } }, legend: { orientation: "h", y: -0.25 } };
  const a = data?.scenario_a.summary;
  const b = data?.scenario_b.summary;

  return <>
    <div className="page-intro"><div className="eyebrow">TRADE STUDY · PHYSICAL ANALYSIS</div><h1>Compare mission scenarios.</h1><p>Choose two site/date windows and inspect the same physical visibility metrics side by side.</p></div>
    <section className="panel controls-panel"><SectionTitle eyebrow="SCENARIO DEFINITIONS" title="A/B mission windows" />
      <div className="scenario-form-grid">
        <div className="scenario-form-card"><div className="scenario-label"><span className="scenario-letter">A</span>Scenario A</div><label className="control-field"><span>Landing site</span><select value={siteA} onChange={(event) => setSiteA(event.target.value)}>{sites.map((site) => <option key={site.site_id} value={site.site_id}>{site.name}</option>)}</select></label><label className="control-field"><span>Start · device local time</span><input type="datetime-local" value={timeA} onChange={(event) => setTimeA(event.target.value)} /></label><label className="control-field"><span>Observation window</span><select value={durationDaysA} onChange={(event) => setDurationDaysA(Number(event.target.value))}>{[1, 3, 5, 7, 10].map((days) => <option key={days} value={days}>{days} day{days > 1 ? "s" : ""}</option>)}</select></label></div>
        <div className="scenario-form-card"><div className="scenario-label scenario-b"><span className="scenario-letter">B</span>Scenario B</div><label className="control-field"><span>Landing site</span><select value={siteB} onChange={(event) => setSiteB(event.target.value)}>{sites.map((site) => <option key={site.site_id} value={site.site_id}>{site.name}</option>)}</select></label><label className="control-field"><span>Start · device local time</span><input type="datetime-local" value={timeB} onChange={(event) => setTimeB(event.target.value)} /></label><label className="control-field"><span>Observation window</span><select value={durationDaysB} onChange={(event) => setDurationDaysB(Number(event.target.value))}>{[1, 3, 5, 7, 10].map((days) => <option key={days} value={days}>{days} day{days > 1 ? "s" : ""}</option>)}</select></label></div>
      </div>
      <div className="scenario-run-row"><span>A: {durationDaysA} day{durationDaysA > 1 ? "s" : ""} · B: {durationDaysB} day{durationDaysB > 1 ? "s" : ""} · {stepMinutes} min sampling. Times are sent as UTC.</span><button className="button button-primary" onClick={() => void run()} disabled={loading}>{loading ? <span className="spinner" /> : <GitCompareArrows size={16} />}{loading ? "Computing both windows…" : "Compare scenarios"}</button></div>
      {error && <div className="notice notice-error">{error}</div>}
    </section>
    {data && a && b ? <>
      <div className="scenario-result-grid">
        <section className="panel scenario-result"><div className="scenario-result-heading"><span className="scenario-letter">A</span><div><div className="eyebrow">BASELINE</div><h3>{data.scenario_a.site.name}</h3><p>{formatUtc(data.scenario_a.summary.start_utc)}</p></div></div><SourceBadge label={data.scenario_a.provenance.horizon_source === "dem" ? `LOLA · ${data.scenario_a.horizon_profile?.coverage_range_km?.toFixed(2) ?? ""} km` : data.scenario_a.provenance.horizon_source} tone={data.scenario_a.provenance.horizon_source === "dem" ? "good" : "warn"} /><div className="compact-metrics"><div><span>Sun visible</span><strong className="value-sun">{pct(a.sun_above_real_horizon_pct)}</strong></div><div><span>Earth visible</span><strong className="value-earth">{pct(a.earth_above_real_horizon_pct)}</strong></div><div><span>Joint visibility</span><strong>{pct(data.scenario_a.simultaneous_visible_pct)}</strong></div><div><span>Longest Sun run</span><strong>{a.sunlit_continuous_hours_max.toFixed(1)} h</strong></div></div></section>
        <section className="panel scenario-result"><div className="scenario-result-heading"><span className="scenario-letter scenario-letter-b">B</span><div><div className="eyebrow">ALTERNATIVE</div><h3>{data.scenario_b.site.name}</h3><p>{formatUtc(data.scenario_b.summary.start_utc)}</p></div></div><SourceBadge label={data.scenario_b.provenance.horizon_source === "dem" ? `LOLA · ${data.scenario_b.horizon_profile?.coverage_range_km?.toFixed(2) ?? ""} km` : data.scenario_b.provenance.horizon_source} tone={data.scenario_b.provenance.horizon_source === "dem" ? "good" : "warn"} /><div className="compact-metrics"><div><span>Sun visible</span><strong className="value-sun">{pct(b.sun_above_real_horizon_pct)}</strong></div><div><span>Earth visible</span><strong className="value-earth">{pct(b.earth_above_real_horizon_pct)}</strong></div><div><span>Joint visibility</span><strong>{pct(data.scenario_b.simultaneous_visible_pct)}</strong></div><div><span>Longest Sun run</span><strong>{b.sunlit_continuous_hours_max.toFixed(1)} h</strong></div></div></section>
      </div>
      <section className="panel"><SectionTitle eyebrow="COMPARATIVE GEOMETRY" title="Sun altitude tracks"><span className="panel-period"><ArrowRightLeft size={13} /> Full UTC samples from each scenario</span></SectionTitle><ScientificChart data={chartData} layout={chartLayout} ariaLabel="Sun altitude comparison for scenarios A and B" height={340} /></section>
      <section className="panel"><SectionTitle eyebrow="DELTA · SCENARIO B MINUS A" title="Metric changes" /><div className="metric-grid metric-grid-4 delta-grid"><MetricCard label="Sun visibility" value={`${data.scenario_b_minus_a.sun_above_real_horizon_pct >= 0 ? "+" : ""}${data.scenario_b_minus_a.sun_above_real_horizon_pct.toFixed(1)} pp`} tone={data.scenario_b_minus_a.sun_above_real_horizon_pct >= 0 ? "sun" : "alert"} /><MetricCard label="Earth visibility" value={`${data.scenario_b_minus_a.earth_above_real_horizon_pct >= 0 ? "+" : ""}${data.scenario_b_minus_a.earth_above_real_horizon_pct.toFixed(1)} pp`} tone={data.scenario_b_minus_a.earth_above_real_horizon_pct >= 0 ? "earth" : "alert"} /><MetricCard label="Longest Sun run" value={`${data.scenario_b_minus_a.sunlit_continuous_hours_max >= 0 ? "+" : ""}${data.scenario_b_minus_a.sunlit_continuous_hours_max.toFixed(1)} h`} /><MetricCard label="Earth blackout" value={`${data.scenario_b_minus_a.earth_blackout_minutes >= 0 ? "+" : ""}${data.scenario_b_minus_a.earth_blackout_minutes.toFixed(0)} min`} tone="neutral" /></div></section>
    </> : <EmptyState title="Comparison ready" detail="The backend will calculate both configurations independently and return the real time series and metric deltas." />}
  </>;
}
