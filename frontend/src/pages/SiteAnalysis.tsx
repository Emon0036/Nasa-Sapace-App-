import { useMemo } from "react";
import type { Data, Layout as PlotLayout } from "plotly.js";
import { DownloadButton, EmptyState, MetricCard, SectionTitle, SourceBadge } from "../components/common";
import { ScientificChart } from "../components/ScientificChart";
import { CelestialPolarChart } from "../components/CelestialPolarChart";
import type { AnalysisResult } from "../types";
import { downloadCsv } from "../utils/csv";
import { formatUtc, pct } from "../utils/format";

interface SiteAnalysisProps {
  results: Record<string, AnalysisResult>;
  selectedSiteId: string;
  onSelectSite: (siteId: string) => void;
}

export function SiteAnalysis({ results, selectedSiteId, onSelectSite }: SiteAnalysisProps) {
  const entries = Object.values(results);
  const result = results[selectedSiteId] ?? entries[0];
  const series = result?.time_series ?? [];

  const terrainApplied = result?.provenance.horizon_source === "dem";
  const timeData = useMemo(() => {
    const data: Data[] = [
      { type: "scatter", mode: "lines", name: "Sun altitude", x: series.map((row) => row.time_utc), y: series.map((row) => row.sun_alt_deg), line: { color: "#f5b84b", width: 2 }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Sun %{y:.2f}°<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Earth altitude", x: series.map((row) => row.time_utc), y: series.map((row) => row.earth_alt_deg), line: { color: "#5ba8ff", width: 2 }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Earth %{y:.2f}°<extra></extra>" },
      { type: "scatter", mode: "lines", name: "Geometric horizon", x: series.map((row) => row.time_utc), y: series.map(() => 0), line: { color: "#8290a5", width: 1, dash: "dot" }, hoverinfo: "skip" },
    ];
    if (terrainApplied && series.some((row) => row.sun_horizon_deg !== undefined)) {
      data.push(
        { type: "scatter", mode: "lines", name: "LOLA horizon at Sun azimuth", x: series.map((row) => row.time_utc), y: series.map((row) => row.sun_horizon_deg ?? 0), line: { color: "#d89628", width: 1.5, dash: "dash" }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Terrain horizon at Sun azimuth %{y:.2f}°<extra></extra>" },
        { type: "scatter", mode: "lines", name: "LOLA horizon at Earth azimuth", x: series.map((row) => row.time_utc), y: series.map((row) => row.earth_horizon_deg ?? 0), line: { color: "#4d87c9", width: 1.5, dash: "dash" }, hovertemplate: "%{x|%b %d %H:%M} UTC<br>Terrain horizon at Earth azimuth %{y:.2f}°<extra></extra>" },
      );
    }
    return data;
  }, [series, terrainApplied]);
  const timeLayout: Partial<PlotLayout> = { yaxis: { title: { text: "Altitude above local horizontal (°)" } }, xaxis: { title: { text: "UTC" } }, legend: { orientation: "h", y: -0.25 } };

  const horizonData = useMemo(() => {
    if (!result?.horizon_profile) return [] as Data[];
    return [{
      type: "scatter",
      mode: "lines",
      name: result.horizon_profile.source === "dem" ? "LOLA-derived DEM horizon" : "Synthetic illustration",
      x: result.horizon_profile.azimuth_deg,
      y: result.horizon_profile.elevation_deg,
      line: { color: result.horizon_profile.source === "dem" ? "#52d6a5" : "#f5b84b", width: 1.7 },
      hovertemplate: "Azimuth %{x:.1f}°<br>Horizon %{y:.2f}°<extra></extra>",
    } as Data];
  }, [result?.horizon_profile]);
  const horizonLayout: Partial<PlotLayout> = {
    xaxis: { title: { text: "Azimuth clockwise from north (°)" }, range: [0, 360] },
    yaxis: { title: { text: "Horizon altitude (°)" }, rangemode: "tozero" },
  };

  if (!result) return <><div className="page-intro"><div className="eyebrow">OBSERVATORY</div><h1>Site analysis</h1><p>Select sites and run a window from the mission controls.</p></div><EmptyState title="No site analysis loaded" detail="Choose one or more candidate sites and run the ephemeris analysis above." /></>;

  const profileSource = result.provenance.horizon_source;
  const visibilityBasis = profileSource === "dem" && result.horizon_profile?.coverage_range_km != null
    ? `LOLA terrain to ${result.horizon_profile.coverage_range_km.toFixed(2)} km`
    : "geometric horizon";
  return <>
    <div className="page-intro page-intro-row">
      <div><div className="eyebrow">OBSERVATORY · PER-SITE CONDITIONS</div><h1>{result.site.name}</h1><p>{result.site.description}</p></div>
      <div className="intro-actions">
        <label className="compact-field"><span>Focus site</span><select value={result.site.site_id} onChange={(event) => onSelectSite(event.target.value)}>{entries.map((entry) => <option key={entry.site.site_id} value={entry.site.site_id}>{entry.site.name}</option>)}</select></label>
        <DownloadButton onClick={() => downloadCsv(`${result.site.site_id}-visibility.csv`, series as unknown as Record<string, unknown>[])} />
      </div>
    </div>
    <div className="data-note"><SourceBadge label={result.summary.backend} tone="good" /><span>{result.provenance.terrain_note}</span><span>{result.site.lat_deg.toFixed(3)}° latitude · {result.site.lon_deg.toFixed(3)}° east · {result.site.elev_m.toFixed(0)} m nominal elevation</span></div>
    <div className="metric-grid metric-grid-4">
      <MetricCard label="Sun above active horizon" value={pct(result.summary.sun_above_real_horizon_pct)} detail={`Geometric: ${pct(result.summary.sun_above_horizon_pct)}`} tone="sun" />
      <MetricCard label="Earth visible" value={pct(result.summary.earth_above_real_horizon_pct)} detail={`Geometric: ${pct(result.summary.earth_above_horizon_pct)}`} tone="earth" />
      <MetricCard label="Longest sunlit interval" value={`${result.summary.sunlit_continuous_hours_max.toFixed(1)} h`} detail="Between sampled visibility transitions" tone="good" />
      <MetricCard label="Longest Earth blackout" value={`${result.summary.earth_blackout_minutes.toFixed(0)} min`} detail={`Joint visibility: ${pct(result.simultaneous_visible_pct)}`} tone="neutral" />
    </div>
    <div className="chart-grid chart-grid-wide">
      <section className="panel chart-panel"><SectionTitle eyebrow="EPHEMERIS TIME SERIES" title="Sun & Earth altitude" /><ScientificChart data={timeData} layout={timeLayout} ariaLabel={`Sun and Earth altitude versus UTC time at ${result.site.name}`} height={360} /></section>
      <section className="panel chart-panel"><SectionTitle eyebrow="LOCAL SKY" title="Azimuth track" /><CelestialPolarChart samples={series} label={`Sun and Earth azimuth and altitude at ${result.site.name}`} /></section>
    </div>
    {result.horizon_profile && <section className="panel chart-panel"><SectionTitle eyebrow="HORIZON PROFILE" title={result.horizon_profile.source === "dem" ? "LOLA terrain obstruction" : "Illustrative horizon profile"}><SourceBadge label={result.provenance.horizon_source === "dem" ? "Applied to visibility" : "Display only · geometric mask active"} tone={result.provenance.horizon_source === "dem" ? "good" : "warn"} /></SectionTitle><ScientificChart data={horizonData} layout={horizonLayout} ariaLabel={`Horizon profile by azimuth at ${result.site.name}`} height={260} /><div className="chart-caption">{result.horizon_profile.source === "dem" ? `${result.horizon_profile.source_detail ?? "LOLA-derived elevation grid"}. Complete terrain coverage extends ${result.horizon_profile.coverage_range_km?.toFixed(2) ?? "—"} km from the observer at ${result.horizon_profile.resolution_m?.toFixed(0) ?? "—"} m/pixel. The DEM reference elevation is ${result.horizon_profile.site_elev_m.toFixed(0)} m; ephemerides use the site's nominal ${result.site.elev_m.toFixed(0)} m elevation. Elevations are interpolated; terrain beyond the stated radius is not represented.` : "Synthetic profile is illustrative, not LOLA terrain; it is not applied to the reported visibility percentages."}{result.horizon_profile.source_url && <> <a href={result.horizon_profile.source_url} target="_blank" rel="noreferrer">Source metadata</a>.</>}</div></section>}
    <section className="panel"><SectionTitle eyebrow="SIMULTANEOUS OPERATIONS" title="Golden windows" /><p className="panel-description">Sampled intervals when both the Sun and Earth clear the active visibility horizon.</p>
      {result.golden_windows.length ? <div className="window-list">{result.golden_windows.map((window, index) => <div className="window-row" key={`${window.start_utc}-${index}`}><span className="window-index">{String(index + 1).padStart(2, "0")}</span><div><strong>{formatUtc(window.start_utc)}</strong><small>through {formatUtc(window.end_utc)}</small></div><span className="window-duration">{window.duration_hours.toFixed(2)} h</span></div>)}</div> : <div className="notice notice-muted">No contiguous joint Sun/Earth intervals were found at this sampling resolution. This does not interpolate between samples.</div>}
      <div className="footnote-strip"><span className="footnote-marker">i</span><p>Visibility basis: {visibilityBasis}. Synthetic horizon graphics are display-only. Golden-window boundaries are sample-resolved.</p></div>
    </section>
    <section className="panel"><SectionTitle eyebrow="DATA EXPORT" title="Ephemeris samples"><span className="table-count">Showing first {Math.min(200, series.length)} of {series.length}</span></SectionTitle>
      <div className="table-scroll"><table className="science-table data-table"><thead><tr><th>Time (UTC)</th><th>Sun alt</th><th>Sun az</th><th>Earth alt</th><th>Earth az</th><th>Sun visible</th><th>Earth visible</th></tr></thead><tbody>{series.slice(0, 200).map((sample) => <tr key={sample.time_utc}><td>{formatUtc(sample.time_utc)}</td><td className="value-sun">{sample.sun_alt_deg.toFixed(3)}°</td><td>{sample.sun_az_deg.toFixed(2)}°</td><td className="value-earth">{sample.earth_alt_deg.toFixed(3)}°</td><td>{sample.earth_az_deg.toFixed(2)}°</td><td>{sample.sun_visible ? "Above" : "Below"}</td><td>{sample.earth_visible ? "Above" : "Below"}</td></tr>)}</tbody></table></div>
      <div className="table-footer"><span>Sample interval: {series.length > 1 ? ((new Date(series[1].time_utc).getTime() - new Date(series[0].time_utc).getTime()) / 60000).toFixed(0) : "—"} min</span><DownloadButton onClick={() => downloadCsv(`${result.site.site_id}-visibility.csv`, series as unknown as Record<string, unknown>[])} label="Download full time series" /></div>
    </section>
  </>;
}
