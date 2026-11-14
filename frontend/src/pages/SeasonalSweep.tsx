import { useMemo, useState } from "react";
import type { Data, Layout as PlotLayout } from "plotly.js";
import { CalendarRange, RefreshCw } from "lucide-react";
import { getSeasonalSweep } from "../services/api";
import type { SeasonalResult, Site } from "../types";
import { EmptyState, SectionTitle, SourceBadge } from "../components/common";
import { ScientificChart } from "../components/ScientificChart";

type SeasonalMetric = "sun_above_real_horizon_pct" | "earth_above_real_horizon_pct" | "sunlit_continuous_hours_max" | "earth_blackout_minutes";

const METRIC_LABELS: Record<SeasonalMetric, string> = {
  sun_above_real_horizon_pct: "Sun visibility (%)",
  earth_above_real_horizon_pct: "Earth visibility (%)",
  sunlit_continuous_hours_max: "Longest Sun run (h)",
  earth_blackout_minutes: "Longest blackout (min)",
};

const HEATMAP_LAYOUT: Partial<PlotLayout> = {
  xaxis: { title: { text: "Sample date (UTC)" }, tickangle: -30 },
  yaxis: { autorange: "reversed" }, margin: { l: 155, r: 55, t: 10, b: 70 },
};

function heatmap(result: SeasonalResult | null, metric: SeasonalMetric, colorscale: string): Data[] {
  if (!result) return [];
  return [{
    type: "heatmap",
    x: result.sites[0]?.samples.map((sample) => sample.date_utc) ?? [],
    y: result.sites.map((entry) => entry.site.name),
    z: result.sites.map((entry) => entry.samples.map((sample) => sample[metric])),
    colorscale,
    zmin: 0,
    ...(metric.endsWith("_pct") ? { zmax: 100 } : {}),
    colorbar: { title: { text: METRIC_LABELS[metric] } },
    hovertemplate: "%{y}<br>%{x}<br>%{z:.2f}<extra></extra>",
  } as Data];
}

interface SeasonalSweepProps {
  sites: Site[];
  selectedSiteIds: string[];
  startUtc: string;
  durationHours: number;
  stepMinutes: number;
  includeTerrain: boolean;
}

export function SeasonalSweep({ sites, selectedSiteIds, startUtc, durationHours, stepMinutes, includeTerrain }: SeasonalSweepProps) {
  const [dateCount, setDateCount] = useState(12);
  const [result, setResult] = useState<SeasonalResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [metric, setMetric] = useState<SeasonalMetric>("sunlit_continuous_hours_max");

  const runSweep = async () => {
    if (!selectedSiteIds.length) {
      setError("Select at least one candidate site in the mission controls.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await getSeasonalSweep({
        site_ids: selectedSiteIds,
        start_utc: startUtc,
        n_dates: dateCount,
        duration_hours: durationHours,
        step_minutes: stepMinutes,
        include_terrain: includeTerrain,
      });
      setResult(response);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Seasonal sweep failed.");
    } finally {
      setLoading(false);
    }
  };

  const dates = result?.sites[0]?.samples.map((sample) => sample.date_utc) ?? [];
  const siteNames = result?.sites.map((entry) => entry.site.name) ?? [];
  const sunHeatmap = useMemo(() => heatmap(result, "sun_above_real_horizon_pct", "Electric"), [result]);
  const earthHeatmap = useMemo(() => heatmap(result, "earth_above_real_horizon_pct", "Blues"), [result]);
  const extraHeatmap = useMemo(() => heatmap(result, metric, metric === "earth_blackout_minutes" ? "Bluered" : "Electric"), [result, metric]);

  return <>
    <div className="page-intro page-intro-row"><div><div className="eyebrow">LUNAR CYCLE · LONG-TERM OPERATIONS</div><h1>Seasonal sweep</h1><p>Explore how visibility metrics change across roughly one lunar month per sample, using the existing date-sweep analysis.</p></div><div className="intro-orbit"><CalendarRange size={24} /><span>{dateCount} EPOCHS</span></div></div>
    <section className="panel controls-panel">
      <SectionTitle eyebrow="SWEEP PARAMETERS" title="Configure seasonal sampling" />
      <div className="inline-controls">
        <label className="control-field"><span>Sampling epochs</span><select value={dateCount} onChange={(event) => setDateCount(Number(event.target.value))}>{[4, 6, 8, 12, 16, 20, 24].map((count) => <option key={count} value={count}>{count} dates · 27.3-day stride</option>)}</select></label>
        <label className="control-field"><span>Additional metric</span><select value={metric} onChange={(event) => setMetric(event.target.value as SeasonalMetric)}>{Object.entries(METRIC_LABELS).filter(([key]) => key !== "sun_above_real_horizon_pct" && key !== "earth_above_real_horizon_pct").map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
        <button className="button button-primary" disabled={loading || !selectedSiteIds.length} onClick={() => void runSweep()}>{loading ? <span className="spinner" /> : <RefreshCw size={15} />}{loading ? "Calculating…" : "Run seasonal sweep"}</button>
      </div>
      <div className="selected-site-line"><span>Sites in sweep</span>{sites.filter((site) => selectedSiteIds.includes(site.site_id)).map((site) => <SourceBadge key={site.site_id} label={site.name} />)}</div>
      {error && <div className="notice notice-error">{error}</div>}
    </section>
    {result ? <>
      <div className="seasonal-heatmap-grid">
        <section className="panel chart-panel"><SectionTitle eyebrow="ILLUMINATION" title="Sun visibility"><span className="panel-period">{dates.length} dates · % of samples</span></SectionTitle><ScientificChart data={sunHeatmap} layout={HEATMAP_LAYOUT} ariaLabel="Sun visibility heatmap by site and lunar date" height={Math.max(330, siteNames.length * 54 + 120)} /></section>
        <section className="panel chart-panel"><SectionTitle eyebrow="COMMUNICATION GEOMETRY" title="Earth visibility"><span className="panel-period">{dates.length} dates · % of samples</span></SectionTitle><ScientificChart data={earthHeatmap} layout={HEATMAP_LAYOUT} ariaLabel="Earth visibility heatmap by site and lunar date" height={Math.max(330, siteNames.length * 54 + 120)} /></section>
      </div>
      {metric !== "sun_above_real_horizon_pct" && metric !== "earth_above_real_horizon_pct" && <section className="panel chart-panel"><SectionTitle eyebrow="ADDITIONAL OPERATIONS METRIC" title={METRIC_LABELS[metric]}><span className="panel-period">{dates.length} dates · {siteNames.length} sites</span></SectionTitle><ScientificChart data={extraHeatmap} layout={HEATMAP_LAYOUT} ariaLabel={`${METRIC_LABELS[metric]} heatmap by site and lunar date`} height={Math.max(330, siteNames.length * 54 + 120)} /></section>}
      <section className="panel"><SectionTitle eyebrow="SOURCE NOTES" title="How to read this sweep" /><div className="note-grid"><div><strong>Ephemeris</strong><p>{result.provenance.source}</p></div><div><strong>Terrain</strong><p>{result.provenance.terrain_note}</p></div><div><strong>Sampling</strong><p>{result.provenance.sampling_note} Cached values retain their six-hour cadence; the selected duration spans the full observation window.</p></div></div></section>
    </> : <EmptyState title="No seasonal sweep loaded" detail="Run a sweep to ask the Python analysis engine for visibility summaries across the date samples." />}
  </>;
}
