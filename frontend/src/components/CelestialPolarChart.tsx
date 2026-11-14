import type { EphemerisSample } from "../types";

interface CelestialPolarChartProps {
  samples: EphemerisSample[];
  label: string;
}

const CENTER_X = 180;
const CENTER_Y = 132;
const RADIUS = 91;

function coordinates(azimuth: number, altitude: number) {
  const radius = Math.min(RADIUS * 1.15, Math.max(0, (90 - altitude) / 90 * RADIUS));
  const angle = (azimuth - 90) * Math.PI / 180;
  return [CENTER_X + Math.cos(angle) * radius, CENTER_Y + Math.sin(angle) * radius] as const;
}

function skyPath(samples: EphemerisSample[], azimuth: (sample: EphemerisSample) => number, altitude: (sample: EphemerisSample) => number) {
  return samples.map((sample, index) => {
    const [x, y] = coordinates(azimuth(sample), altitude(sample));
    return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

export function CelestialPolarChart({ samples, label }: CelestialPolarChartProps) {
  const sunPath = skyPath(samples, (sample) => sample.sun_az_deg, (sample) => sample.sun_alt_deg);
  const earthPath = skyPath(samples, (sample) => sample.earth_az_deg, (sample) => sample.earth_alt_deg);
  const last = samples.at(-1);
  const horizonRadius = RADIUS;
  const north = coordinates(0, 0);
  const east = coordinates(90, 0);
  const south = coordinates(180, 0);
  const west = coordinates(270, 0);

  return <div className="polar-chart-wrap">
    <svg className="polar-chart" viewBox="0 0 360 270" role="img" aria-label={label}>
      <defs><radialGradient id="sky-radar-fill"><stop offset="0" stopColor="#0d2038" stopOpacity=".14" /><stop offset="1" stopColor="#16365a" stopOpacity=".32" /></radialGradient></defs>
      <circle cx={CENTER_X} cy={CENTER_Y} r={horizonRadius} fill="url(#sky-radar-fill)" stroke="rgba(177,196,221,.5)" strokeDasharray="4 4" />
      {[0, 30, 60, 90].map((altitude) => {
        const radius = (90 - altitude) / 90 * RADIUS;
        return <g key={altitude}><circle cx={CENTER_X} cy={CENTER_Y} r={radius} fill="none" stroke="rgba(148,163,184,.14)" /><text x={CENTER_X + 5} y={CENTER_Y - radius - 3} className="polar-label">{altitude}°</text></g>;
      })}
      {[north, east, south, west].map(([x, y], index) => <line key={index} x1={CENTER_X} y1={CENTER_Y} x2={x} y2={y} stroke="rgba(148,163,184,.14)" />)}
      <text x={CENTER_X} y={CENTER_Y - RADIUS - 12} textAnchor="middle" className="polar-direction">N</text>
      <text x={CENTER_X + RADIUS + 14} y={CENTER_Y + 3} className="polar-direction">E</text>
      <text x={CENTER_X} y={CENTER_Y + RADIUS + 17} textAnchor="middle" className="polar-direction">S</text>
      <text x={CENTER_X - RADIUS - 15} y={CENTER_Y + 3} className="polar-direction">W</text>
      {samples.length > 0 && <>
        <path d={sunPath} fill="none" stroke="#f5b84b" strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round" opacity=".82" />
        <path d={earthPath} fill="none" stroke="#5ba8ff" strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round" opacity=".82" />
      </>}
      {last && <>
        <circle cx={coordinates(last.sun_az_deg, last.sun_alt_deg)[0]} cy={coordinates(last.sun_az_deg, last.sun_alt_deg)[1]} r="3.5" fill="#f5b84b" stroke="#07101e" strokeWidth="1.5" />
        <circle cx={coordinates(last.earth_az_deg, last.earth_alt_deg)[0]} cy={coordinates(last.earth_az_deg, last.earth_alt_deg)[1]} r="3.5" fill="#5ba8ff" stroke="#07101e" strokeWidth="1.5" />
      </>}
    </svg>
    <div className="polar-legend"><span><i className="legend-line legend-sun" />Sun track</span><span><i className="legend-line legend-earth" />Earth track</span><span className="polar-explanation">Center = zenith · outer circle = geometric horizon</span></div>
  </div>;
}
