import { useState } from "react";
import { BadgeCheck, RefreshCw, TriangleAlert } from "lucide-react";
import { getRecommendation } from "../services/api";
import type { ModelMetrics, RecommendationResult, Site } from "../types";
import { EmptyState, MetricCard, SectionTitle, SourceBadge } from "../components/common";
import { formatUtc, pct } from "../utils/format";

interface AIRecommendationsProps {
  sites: Site[];
  selectedSiteIds: string[];
  startUtc: string;
  durationHours: number;
  stepMinutes: number;
  includeTerrain: boolean;
  modelAvailable: boolean;
  metrics: ModelMetrics | null;
}

export function AIRecommendations({ sites, selectedSiteIds, startUtc, durationHours, stepMinutes, includeTerrain, modelAvailable, metrics }: AIRecommendationsProps) {
  const [result, setResult] = useState<RecommendationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const run = async () => {
    if (!selectedSiteIds.length) {
      setError("Select at least one model-supported site in the mission controls.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      setResult(await getRecommendation({
        site_ids: selectedSiteIds,
        start_utc: startUtc,
        duration_hours: durationHours,
        sample_hours: 3,
        step_minutes: stepMinutes,
        include_terrain: includeTerrain,
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Recommendation service failed.");
    } finally {
      setLoading(false);
    }
  };

  if (!modelAvailable) return <>
    <div className="page-intro"><div className="eyebrow">DECISION SUPPORT · RANDOM FOREST SURROGATE</div><h1>ML recommendations</h1><p>Rank site/date options with the saved Horizons-trained surrogate, then verify the shortlist with the physical ephemeris engine.</p></div>
    <EmptyState title="Model artifact is unavailable" detail="The backend did not confirm a loadable trained model. No predictions or recommendation scores are shown." />
  </>;

  return <>
    <div className="page-intro page-intro-row"><div><div className="eyebrow">DECISION SUPPORT · RANDOM FOREST SURROGATE</div><h1>ML recommendations</h1><p>Predictions are a shortlisting aid. The top candidates are recomputed through the physical ephemeris engine before ranking.</p></div><button className="button button-primary" onClick={() => void run()} disabled={loading || !selectedSiteIds.length}>{loading ? <span className="spinner" /> : <RefreshCw size={15} />}{loading ? "Ranking & verifying…" : "Rank and physically verify"}</button></div>
    {metrics && <>
      <section className="panel"><SectionTitle eyebrow="SAVED HELD-OUT EVALUATION" title="Surrogate model performance"><SourceBadge label={`${metrics.dataset_rows.toLocaleString()} Horizons-derived samples`} tone="good" /></SectionTitle>
        <div className="metric-grid metric-grid-4"><MetricCard label="Sun altitude MAE" value={`${metrics.altitude_metrics.sun_altitude_deg?.model_mae_deg.toFixed(3) ?? "—"}°`} detail="Grouped held-out UTC dates" tone="sun" /><MetricCard label="Earth altitude MAE" value={`${metrics.altitude_metrics.earth_altitude_deg?.model_mae_deg.toFixed(3) ?? "—"}°`} detail="Grouped held-out UTC dates" tone="earth" /><MetricCard label="Sun azimuth circular MAE" value={`${metrics.azimuth_metrics.sun_azimuth_circular_mae_deg.toFixed(2)}°`} /><MetricCard label="Training date coverage" value={metrics.date_coverage_utc.map((date) => date.slice(0, 10)).join(" — ")} detail={`${metrics.site_count} sampled sites`} /></div>
        <div className="notice notice-muted"><TriangleAlert size={15} /><span>{metrics.interpretation} The model is not a future-forecast tool and does not replace Horizons/SPICE.</span></div>
      </section>
      <section className="panel controls-panel"><SectionTitle eyebrow="SCENARIO INPUTS" title="Candidate sites" /><div className="selected-site-line"><span>Selected from mission controls</span>{sites.filter((site) => selectedSiteIds.includes(site.site_id)).map((site) => <SourceBadge key={site.site_id} label={site.name} />)}</div><p className="panel-description">The model excludes sites outside its saved date and coordinate coverage. Unsupported selections are reported instead of extrapolated.</p>{error && <div className="notice notice-error">{error}</div>}</section>
    </>}
    {result ? <>
      <section className="panel"><SectionTitle eyebrow="PHYSICALLY RECOMPUTED SHORTLIST" title="Recommendations"><SourceBadge label="Physical verification" tone="good" /></SectionTitle>
        {result.recommended && <div className="recommendation-winner"><div className="winner-icon"><BadgeCheck size={21} /></div><div className="winner-copy"><div className="eyebrow">TOP PHYSICALLY CHECKED OPTION</div><h3>{result.recommended.summary.site_name}</h3><p>{formatUtc(result.recommended.summary.start_utc)} · {result.recommended.terrain_note}</p></div><div className="winner-score"><span>PHYSICAL SCORE</span><strong>{result.recommended.physical_score.toFixed(1)}<small>/100</small></strong></div></div>}
        {result.physical_checks.length ? <div className="table-scroll"><table className="science-table"><thead><tr><th>ML rank</th><th>Candidate</th><th>Start (UTC)</th><th>ML score</th><th>Physical Sun</th><th>Physical Earth</th><th>Joint visibility</th><th>Physical score</th></tr></thead><tbody>{result.physical_checks.map((check, index) => <tr key={`${check.summary.site_id}-${check.summary.start_utc}`}><td><span className="rank-badge">{index + 1}</span></td><td><strong>{check.summary.site_name}</strong><small>{Number(check.ml_candidate.delay_hours).toFixed(0)} h delay</small></td><td>{formatUtc(check.summary.start_utc)}</td><td>{Number(check.ml_candidate.score).toFixed(1)}</td><td className="value-sun">{pct(check.summary.sun_above_real_horizon_pct)}</td><td className="value-earth">{pct(check.summary.earth_above_real_horizon_pct)}</td><td>{pct(check.simultaneous_visible_pct)}</td><td className="value-good">{check.physical_score.toFixed(1)}</td></tr>)}</tbody></table></div> : <EmptyState title="No candidates could be physically verified" detail="The selected sites may be outside model coverage or the ephemeris backend may be unavailable." />}
        {result.excluded_sites.length > 0 && <div className="notice notice-muted">Outside the model’s sampled coordinate coverage: {result.excluded_sites.join(", ")}</div>}
      </section>
      <section className="panel"><SectionTitle eyebrow="SCORING TRANSPARENCY" title="How the recommendation is formed" /><p className="panel-description">{result.score_definition}</p><div className="note-grid">{result.limitations.map((limitation) => <div key={limitation}><TriangleAlert size={15} /><p>{limitation}</p></div>)}</div></section>
    </> : <EmptyState title="Ready to rank candidates" detail="The real saved model will rank selected sites and the API will re-run the highest three candidates with physical ephemerides." />}
  </>;
}
