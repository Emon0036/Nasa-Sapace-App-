import type { MissionPlan, SurfaceTelemetry } from "../types";

export function MissionSkyRadar({ telemetry, plan, projected }: { telemetry?: SurfaceTelemetry; plan: MissionPlan; projected: boolean }) {
  if (!telemetry) return <div className="mission-radar-unavailable">Surface ephemeris is unavailable for this mission plan.</div>;
  const width = 720;
  const height = 470;
  const cx = width / 2;
  const cy = height * .76;
  const radius = 174;
  const point = (azimuth: number, altitude: number) => {
    const r = radius * (90 - Math.max(-12, Math.min(90, altitude))) / 90;
    const angle = (azimuth - 90) * Math.PI / 180;
    return [cx + Math.cos(angle) * r, cy + Math.sin(angle) * r] as const;
  };
  const horizon = plan.horizon_profile.azimuth_deg.map((azimuth, index) => {
    const [x, y] = point(azimuth, plan.horizon_profile.elevation_deg[index] ?? 0);
    return `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const [sunX, sunY] = point(telemetry.sun_az_deg, telemetry.sun_alt_deg);
  const [earthX, earthY] = point(telemetry.earth_az_deg, telemetry.earth_alt_deg);
  const horizonSource = plan.horizon_profile.source === "dem" ? "LOLA terrain mask" : "geometric horizon";
  return <div className="mission-sky-radar" data-radar-basis={horizonSource}>
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sun and Earth direction relative to the local lunar horizon">
      {[0, 30, 60, 90].map((altitude) => <g key={altitude}><circle cx={cx} cy={cy} r={radius * (90 - altitude) / 90} className="radar-ring" /><text x={cx + 8} y={cy - radius * (90 - altitude) / 90 - 7} className="radar-alt-label">{altitude}°</text></g>)}
      {[0, 90, 180, 270].map((azimuth) => { const [x, y] = point(azimuth, 0); return <line key={azimuth} x1={cx} y1={cy} x2={x} y2={y} className="radar-spoke" />; })}
      <text x={cx} y={cy - radius - 16} textAnchor="middle" className="radar-cardinal">N</text>
      <text x={cx + radius + 20} y={cy + 5} textAnchor="middle" className="radar-cardinal">E</text>
      <text x={cx} y={cy + radius + 28} textAnchor="middle" className="radar-cardinal">S</text>
      <text x={cx - radius - 20} y={cy + 5} textAnchor="middle" className="radar-cardinal">W</text>
      <path d={`${horizon} Z`} className={`radar-terrain ${plan.horizon_profile.source === "dem" ? "radar-terrain-dem" : ""}`} />
      <circle cx={sunX} cy={sunY} r="10" className={`radar-body radar-sun ${telemetry.sun_visible ? "" : "radar-body-blocked"}`} />
      <text x={sunX + 14} y={sunY - 12} className="radar-body-label radar-sun-label">SUN · {telemetry.sun_alt_deg.toFixed(1)}°</text>
      <circle cx={earthX} cy={earthY} r="10" className={`radar-body radar-earth ${telemetry.earth_visible ? "" : "radar-body-blocked"}`} />
      <text x={earthX + 14} y={earthY + 23} className="radar-body-label radar-earth-label">EARTH · {telemetry.earth_alt_deg.toFixed(1)}°</text>
    </svg>
    <div className="radar-footer"><span>{horizonSource}</span><span>{projected ? "Projected landing conditions" : "Calculated surface conditions"}</span></div>
    <div className="radar-legend"><span className="radar-legend-sun">Sun</span><span className="radar-legend-earth">Earth</span><span className="radar-legend-horizon">Local horizon mask</span></div>
  </div>;
}
