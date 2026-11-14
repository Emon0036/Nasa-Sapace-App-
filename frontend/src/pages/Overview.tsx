import { Activity, Clock3, Globe2, Sun } from "lucide-react";
import type { Data, Layout as PlotLayout } from "plotly.js";
import type { AnalysisResult, Site } from "../types";
import { ScientificChart } from "../components/ScientificChart";
import { DownloadButton, EmptyState, MetricCard, SectionTitle, SourceBadge } from "../components/common";
import type { PageKey } from "../components/Layout";
import { downloadCsv } from "../utils/csv";
import { pct } from "../utils/format";

interface OverviewProps {
  sites: Site[];
  results: Record<string, AnalysisResult>;
  loading: boolean;
  errors: Record<string, string>;
  onPageChange: (page: PageKey) => void;
  onSelectSite: (siteId: string) => void;
}

export function Overview({ sites, results, loading, errors, onPageChange, onSelectSite }: OverviewProps) {
  const rows = Object.values(results);
  const bestSun = rows.reduce<AnalysisResult | null>((best, current) => !best || current.summary.sun_above_real_horizon_pct > best.summary.sun_above_real_horizon_pct ? current : best, null);
  const bestEarth = rows.reduce<AnalysisResult | null>((best, current) => !best || current.summary.earth_above_real_horizon_pct > best.summary.earth_above_real_horizon_pct ? current : best, null);
  const bestJoint = rows.reduce<AnalysisResult | null>((best, current) => !best || current.simultaneous_visible_pct > best.simultaneous_visible_pct ? current : best, null);
  const longestSun = rows.reduce<AnalysisResult | null>((best, current) => !best || current.summary.sunlit_continuous_hours_max > best.summary.sunlit_continuous_hours_max ? current : best, null);
  const chartData = [
    { type: "bar", name: "Sun above selected horizon", x: rows.map((item) => item.site.name), y: rows.map((item) => item.summary.sun_above_real_horizon_pct), marker: { color: "#f5b84b" }, hovertemplate: "%{x}<br>Sun visible: %{y:.1f}%<extra></extra>" },
    { type: "bar", name: "Earth visible", x: rows.map((item) => item.site.name), y: rows.map((item) => item.summary.earth_above_real_horizon_pct), marker: { color: "#5ba8ff" }, hovertemplate: "%{x}<br>Earth visible: %{y:.1f}%<extra></extra>" },
  ] as Data[];
  const chartLayout: Partial<PlotLayout> = {
    barmode: "group", yaxis: { title: { text: "Time visible (%)" }, range: [0, 100] },
    xaxis: { tickangle: -18 }, legend: { orientation: "h", y: -0.34 }, margin: { l: 52, r: 18, t: 10, b: 90 },
  };

  if (!rows.length) {
    return <>
      <div className="page-intro"><div className="eyebrow">LUNAR SOUTH POLE · VISIBILITY PLANNING</div><h1>Plan the surface window.</h1><p>Compare sunlight, direct-to-Earth visibility, and operational overlap using the existing Horizons/SPICE analysis engine.</p></div>
      <EmptyState title={loading ? "Computing the selected sites" : "No analysis results yet"} detail={loading ? "The backend is calculating ephemerides for your mission window." : "Choose sites and a UTC window above, then run the scientific analysis."} />
      {Object.keys(errors).length > 0 && <div className="notice notice-error">{Object.entries(errors).map(([id, message]) => <p key={id}><strong>{id}:</strong> {message}</p>)}</div>}
      <section className="panel panel-quiet"><SectionTitle eyebrow="AVAILABLE SITES" title="Candidate locations" /><div className="site-chip-grid">{sites.map((site) => <div className="site-chip" key={site.site_id}><span className="site-chip-code">{site.site_id.slice(0, 2).toUpperCase()}</span><span><strong>{site.name}</strong><small>{site.lat_deg.toFixed(2)}°, {site.lon_deg.toFixed(2)}° E</small></span></div>)}</div></section>
    </>;
  }

  return <>
    <div className="page-intro page-intro-row">
      <div><div className="eyebrow">LUNAR SOUTH POLE · VISIBILITY PLANNING</div><h1>Plan the surface window.</h1><p>Compare sunlight, direct-to-Earth visibility, and operational overlap across selected candidate sites.</p></div>
      <div className="intro-actions"><SourceBadge label={rows[0].summary.backend} tone="good" /><DownloadButton label="Export summary" onClick={() => downloadCsv("lunar-horizon-site-summary.csv", rows.map((row) => ({ site: row.site.name, ...row.summary, simultaneous_visible_pct: row.simultaneous_visible_pct, horizon_source: row.provenance.horizon_source })))} /></div>
    </div>
    <div className="metric-grid metric-grid-4">
      <MetricCard label="Best sunlight availability" value={bestSun ? pct(bestSun.summary.sun_above_real_horizon_pct) : "—"} detail={bestSun?.site.name} tone="sun" icon={<Sun size={17} />} />
      <MetricCard label="Best Earth visibility" value={bestEarth ? pct(bestEarth.summary.earth_above_real_horizon_pct) : "—"} detail={bestEarth?.site.name} tone="earth" icon={<Globe2 size={17} />} />
      <MetricCard label="Best simultaneous window" value={bestJoint ? pct(bestJoint.simultaneous_visible_pct) : "—"} detail={bestJoint?.site.name} tone="good" icon={<Activity size={17} />} />
      <MetricCard label="Longest sunlit run" value={longestSun ? `${longestSun.summary.sunlit_continuous_hours_max.toFixed(1)} h` : "—"} detail={longestSun?.site.name} tone="neutral" icon={<Clock3 size={17} />} />
    </div>
    <section className="panel chart-panel">
      <SectionTitle eyebrow="SITE PERFORMANCE" title="Visibility across the selected window"><span className="panel-period">{rows[0].summary.duration_hours.toFixed(0)} HOURS · {rows.length} SITES</span></SectionTitle>
      <ScientificChart data={chartData} layout={chartLayout} ariaLabel="Grouped bar chart comparing Sun and Earth visibility by landing site" height={350} />
    </section>
    <section className="panel">
      <SectionTitle eyebrow="MISSION WINDOW" title="Site comparison"><span className="table-count">{rows.length} sites analyzed</span></SectionTitle>
      <div className="table-scroll"><table className="science-table"><thead><tr><th>Candidate site</th><th>Sun visible</th><th>Earth visible</th><th>Joint visibility</th><th>Longest Sun run</th><th>Earth blackout</th><th>Analysis basis</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.site.site_id} onClick={() => { onSelectSite(row.site.site_id); onPageChange("site"); }} className="clickable-row">
          <td><strong>{row.site.name}</strong><small>{row.site.lat_deg.toFixed(2)}°, {row.site.lon_deg.toFixed(2)}° E · {row.site.elev_m.toFixed(0)} m</small></td>
          <td className="value-sun">{pct(row.summary.sun_above_real_horizon_pct)}</td><td className="value-earth">{pct(row.summary.earth_above_real_horizon_pct)}</td><td className="value-good">{pct(row.simultaneous_visible_pct)}</td>
          <td>{row.summary.sunlit_continuous_hours_max.toFixed(1)} h</td><td>{row.summary.earth_blackout_minutes.toFixed(0)} min</td>
          <td><SourceBadge label={row.provenance.horizon_source === "dem" ? `LOLA · ${row.horizon_profile?.coverage_range_km?.toFixed(2) ?? ""} km` : row.provenance.horizon_source} tone={row.provenance.horizon_source === "dem" ? "good" : "warn"} /></td>
        </tr>)}</tbody></table></div>
      {Object.keys(errors).length > 0 && <div className="notice notice-error notice-inline">{Object.entries(errors).map(([id, message]) => <p key={id}><strong>{id}:</strong> {message}</p>)}</div>}
    </section>
    <div className="footnote-strip"><span className="footnote-marker">i</span><p>LOLA profiles apply only within their displayed radius; sites outside tile coverage use the geometric horizon. Synthetic graphics are illustrative, and Earth visibility is not a communications link budget.</p></div>
  </>;
}
