import { lazy, Suspense } from "react";
import {
  Activity, Compass, Crosshair, Globe, MapPin, Orbit, Pause, Play, Radio,
  RotateCcw, Rocket, Satellite, SkipBack, SkipForward, Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { MissionPhase, MissionPlan, SurfaceTelemetry } from "../types";
import type { MissionCameraMode } from "./MissionScene3D";
import { MissionSkyRadar } from "./MissionSkyRadar";
import { SourceBadge } from "./common";
import { formatUtc } from "../utils/format";

const MissionScene3D = lazy(() => import("./MissionScene3D").then((module) => ({ default: module.MissionScene3D })));

const CAMERA_MODES: Array<{ id: MissionCameraMode | "sky-radar"; label: string; icon: LucideIcon }> = [
  { id: "overview", label: "Mission Overview", icon: Globe },
  { id: "follow", label: "Follow Spacecraft", icon: Satellite },
  { id: "launch", label: "Earth Launch", icon: Rocket },
  { id: "orbit", label: "Lunar Orbit", icon: Orbit },
  { id: "descent", label: "Lunar Descent", icon: Crosshair },
  { id: "surface", label: "Surface Ops", icon: MapPin },
  { id: "sky-radar", label: "Sky Radar", icon: Compass },
];

const PLAYBACK_RATES = [
  { value: 1, label: "1× · real time" },
  { value: 600, label: "600× · 10 min / sec" },
  { value: 3600, label: "3,600× · 1 hr / sec" },
  { value: 21600, label: "21,600× · 6 hr / sec" },
];

interface MissionExperienceProps {
  plan: MissionPlan;
  seconds: number;
  phase: MissionPhase;
  telemetry?: SurfaceTelemetry;
  projected: boolean;
  cameraMode: MissionCameraMode | "sky-radar";
  onCameraModeChange: (mode: MissionCameraMode | "sky-radar") => void;
  playing: boolean;
  playbackRate: number;
  onTogglePlayback: () => void;
  onReset: () => void;
  onPreviousPhase: () => void;
  onNextPhase: () => void;
  onSeek: (seconds: number) => void;
  onPlaybackRateChange: (rate: number) => void;
}

function formatMissionElapsed(seconds: number) {
  const elapsed = Math.max(0, Math.floor(seconds));
  const days = Math.floor(elapsed / 86400);
  const hours = Math.floor((elapsed % 86400) / 3600);
  const minutes = Math.floor((elapsed % 3600) / 60);
  const secs = elapsed % 60;
  return `T+${days}d ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatSigned(value?: number) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "Unavailable";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}°`;
}

function phaseDuration(phase: MissionPhase) {
  const seconds = Math.max(0, phase.end_seconds - phase.start_seconds);
  if (seconds >= 86400) return `${(seconds / 86400).toFixed(seconds % 86400 === 0 ? 0 : 1)} days`;
  if (seconds >= 3600) return `${(seconds / 3600).toFixed(1)} hours`;
  return `${Math.max(1, Math.round(seconds / 60))} min`;
}

function HorizonSource({ plan }: { plan: MissionPlan }) {
  const profile = plan.horizon_profile;
  const label = profile.source === "dem"
    ? `LOLA terrain${profile.coverage_range_km ? ` · ${profile.coverage_range_km.toFixed(profile.coverage_range_km < 1 ? 2 : 1)} km` : ""}`
    : profile.source === "synthetic" ? "Geometric visibility · synthetic display only" : "Geometric horizon";
  return <SourceBadge label={label} tone={profile.source === "dem" ? "good" : "neutral"} />;
}

function TelemetryCard({
  title, icon: Icon, value, detail, status, tone = "neutral",
}: {
  title: string;
  icon: LucideIcon;
  value: string;
  detail: string;
  status?: string;
  tone?: "neutral" | "sun" | "earth" | "good" | "warn";
}) {
  return <article className={`mission-telemetry-card telemetry-${tone}`}>
    <div className="mission-telemetry-card-heading"><span className="mission-telemetry-icon"><Icon size={17} /></span><span>{title}</span>{status && <small>{status}</small>}</div>
    <strong className="mission-telemetry-value">{value}</strong>
    <span className="mission-telemetry-detail">{detail}</span>
  </article>;
}

function MissionTelemetry({ plan, phase, seconds, telemetry, projected }: {
  plan: MissionPlan;
  phase: MissionPhase;
  seconds: number;
  telemetry?: SurfaceTelemetry;
  projected: boolean;
}) {
  const sunClearance = telemetry && typeof telemetry.sun_horizon_deg === "number"
    ? telemetry.sun_alt_deg - telemetry.sun_horizon_deg
    : undefined;
  const earthClearance = telemetry && typeof telemetry.earth_horizon_deg === "number"
    ? telemetry.earth_alt_deg - telemetry.earth_horizon_deg
    : undefined;
  const sampleUtc = telemetry?.time_utc ? formatUtc(telemetry.time_utc) : "Unavailable";
  const latitude = Number.isFinite(plan.site.lat_deg) ? `${Math.abs(plan.site.lat_deg).toFixed(3)}° ${plan.site.lat_deg < 0 ? "S" : "N"}` : "Unavailable";
  const longitude = Number.isFinite(plan.site.lon_deg) ? `${plan.site.lon_deg.toFixed(3)}° east-positive` : "Unavailable";
  const conditionSource = projected ? "PROJECTED AT LANDING" : "CALCULATED SURFACE SAMPLE";

  return <aside className="mission-telemetry-sidebar" aria-label="Mission telemetry">
    <section className="mission-telemetry-panel mission-status-panel">
      <div className="mission-telemetry-panel-heading"><Activity size={17} /><span>Mission telemetry</span></div>
      <div className="mission-status-main"><span>MISSION ELAPSED</span><strong>{formatMissionElapsed(seconds)}</strong></div>
      <div className="mission-status-grid"><div><span>Current phase</span><strong>{phase.name}</strong></div><div><span>UTC timestamp</span><strong>{formatUtc(new Date(Date.parse(plan.launch_utc) + seconds * 1000).toISOString())}</strong></div></div>
      <div className="mission-data-source"><span className="mission-live-dot" />{conditionSource}</div>
    </section>

    <TelemetryCard
      title="Sun altitude"
      icon={Sun}
      tone="sun"
      value={formatSigned(telemetry?.sun_alt_deg)}
      detail={telemetry ? `Horizon clearance ${formatSigned(sunClearance)}` : "Surface ephemeris unavailable"}
      status={telemetry ? (telemetry.sun_visible ? "ABOVE HORIZON" : "BELOW HORIZON") : "UNAVAILABLE"}
    />
    <TelemetryCard
      title="Earth visibility"
      icon={Radio}
      tone="earth"
      value={telemetry ? formatSigned(telemetry.earth_alt_deg) : "Unavailable"}
      detail={telemetry ? `Horizon clearance ${formatSigned(earthClearance)}` : "Surface ephemeris unavailable"}
      status={telemetry ? (telemetry.earth_visible ? "GEOMETRIC LOS CLEAR" : "GEOMETRIC LOS BLOCKED") : "UNAVAILABLE"}
    />

    <section className="mission-telemetry-panel mission-site-card">
      <div className="mission-telemetry-panel-heading"><MapPin size={17} /><span>Landing site</span></div>
      <strong className="mission-site-name">{plan.site.name}</strong>
      <div className="mission-coordinate-grid"><div><span>Latitude</span><strong>{latitude}</strong></div><div><span>Longitude</span><strong>{longitude}</strong></div><div><span>Elevation</span><strong>{Number.isFinite(plan.site.elev_m) ? `${plan.site.elev_m.toLocaleString()} m` : "Unavailable"}</strong></div></div>
      <HorizonSource plan={plan} />
    </section>

    <section className="mission-condition-card">
      <div className="mission-condition-heading"><span>{projected ? "Projected surface conditions" : "Current surface conditions"}</span><small>{sampleUtc}</small></div>
      {telemetry ? <div className="mission-condition-list">
        <div><span className={`condition-indicator ${telemetry.sun_visible ? "condition-positive" : "condition-muted"}`} />Sun {telemetry.sun_visible ? "clears" : "is below"} the modeled horizon</div>
        <div><span className={`condition-indicator ${telemetry.earth_visible ? "condition-positive" : "condition-muted"}`} />Earth {telemetry.earth_visible ? "is geometrically visible" : "is geometrically occulted"}</div>
      </div> : <p>Unavailable until the backend returns surface ephemeris samples.</p>}
      <small>Line of sight is geometric visibility; this is not an RF link budget.</small>
    </section>
  </aside>;
}

function MissionTimeline({ plan, phase, seconds, playing, playbackRate, onTogglePlayback, onReset, onPreviousPhase, onNextPhase, onSeek, onPlaybackRateChange }: MissionExperienceProps) {
  return <section className="mission-timeline-panel" aria-label="Mission timeline controls">
    <div className="mission-timeline-heading"><div><span>MISSION TIMELINE</span><strong>{formatMissionElapsed(seconds)} <i>/</i> {formatMissionElapsed(plan.duration_seconds)}</strong></div><div className="mission-timeline-utc">{formatUtc(new Date(Date.parse(plan.launch_utc) + seconds * 1000).toISOString())}</div></div>
    <div className="mission-phase-markers" aria-label="Mission phase markers">
      {plan.phases.map((item, index) => <button key={item.name} type="button" className={`mission-phase-marker ${item.name === phase.name ? "mission-phase-marker-active" : ""} ${seconds >= item.end_seconds ? "mission-phase-marker-complete" : ""}`} onClick={() => onSeek(item.start_seconds)} aria-current={item.name === phase.name ? "step" : undefined}>
        <span className="mission-phase-marker-index">{String(index + 1).padStart(2, "0")}</span><span className="mission-phase-marker-copy"><strong>{item.name === "POWERED DESCENT" ? "Descent" : item.name === "SURFACE OPS" ? "Surface operations" : item.name === "LUNAR ORBIT" ? "Lunar orbit" : item.name[0] + item.name.slice(1).toLowerCase()}</strong><small>{phaseDuration(item)}{item.illustrative ? " · illustrative" : " · ephemeris"}</small></span>
      </button>)}
    </div>
    <div className="mission-scrubber-row"><span className="mission-scrubber-current">{formatMissionElapsed(seconds)}</span><input className="mission-scrubber" type="range" min={0} max={plan.duration_seconds} step={1} value={seconds} onChange={(event) => onSeek(Number(event.target.value))} aria-label="Seek mission elapsed time"/><span className="mission-scrubber-total">{formatMissionElapsed(plan.duration_seconds)}</span></div>
    <div className="mission-playback-row">
      <div className="mission-playback-controls">
        <button className="mission-control-button" onClick={onPreviousPhase} aria-label="Go to previous mission phase"><SkipBack size={17} /><span>Previous phase</span></button>
        <button className="mission-control-button" onClick={onReset} aria-label="Reset mission timeline"><RotateCcw size={17} /><span>Reset</span></button>
        <button className="mission-play-button" onClick={onTogglePlayback} aria-label={playing ? "Pause mission playback" : "Play mission playback"}>{playing ? <Pause size={18} /> : <Play size={18} />}{playing ? "Pause" : "Play"}</button>
        <button className="mission-control-button" onClick={onNextPhase} aria-label="Go to next mission phase"><SkipForward size={17} /><span>Next phase</span></button>
      </div>
      <label className="mission-speed-control"><span>Playback speed</span><select value={playbackRate} onChange={(event) => onPlaybackRateChange(Number(event.target.value))}>{PLAYBACK_RATES.map((rate) => <option key={rate.value} value={rate.value}>{rate.label}</option>)}</select></label>
    </div>
  </section>;
}

export function MissionExperience(props: MissionExperienceProps) {
  const { plan, phase, seconds, telemetry, projected, cameraMode, onCameraModeChange } = props;
  return <section className="mission-console">
    <div className="mission-console-heading">
      <div><div className="mission-console-eyebrow">MISSION SIMULATION · NOT TO SCALE</div><h2>Earth to the lunar south pole</h2><p>{plan.site.name} · {formatUtc(plan.launch_utc)} launch · {plan.provenance.ephemeris_backend}</p></div>
      <div className="mission-console-badges"><span className="mission-phase-live"><i />{phase.name}</span><HorizonSource plan={plan} /></div>
    </div>
    <nav className="mission-camera-toolbar" aria-label="Simulation camera views">
      {CAMERA_MODES.map(({ id, label, icon: Icon }) => <button type="button" key={id} className={`mission-camera-button ${cameraMode === id ? "mission-camera-button-active" : ""}`} onClick={() => onCameraModeChange(id)} aria-pressed={cameraMode === id}>
        <Icon size={16} aria-hidden="true" /><span>{label}</span>
      </button>)}
    </nav>
    <div className="mission-visual-and-telemetry">
      <div className="mission-visual-column">
        {cameraMode === "sky-radar" ? <MissionSkyRadar telemetry={telemetry} plan={plan} projected={projected} /> : <Suspense fallback={<div className="mission-scene-loading" role="status">Preparing the 3D mission viewport…</div>}><MissionScene3D plan={plan} seconds={seconds} phase={phase} cameraMode={cameraMode} /></Suspense>}
        <div className="mission-scene-legend" aria-label="Scene legend"><span><i className="legend-earth" />Earth departure</span><span><i className="legend-transit" />Translunar transit</span><span><i className="legend-orbit" />Lunar orbit</span><span><i className="legend-descent" />Descent</span><span><i className="legend-spacecraft" />Spacecraft</span><span><i className="legend-surface" />Landing site</span></div>
        <div className="mission-trajectory-note"><Orbit size={14} /><span>Vehicle path is illustrative and not a validated flight trajectory. Distances are not to scale.</span></div>
      </div>
      <MissionTelemetry plan={plan} phase={phase} seconds={seconds} telemetry={telemetry} projected={projected} />
    </div>
    <MissionTimeline {...props} />
    <div className="mission-science-source"><span>SCIENCE SOURCE</span><span>{plan.provenance.surface_data}</span><span>{plan.provenance.horizon_note}</span><span>Visual textures: NASA/GSFC Blue Marble · NASA LRO/LROC color map.</span></div>
  </section>;
}
