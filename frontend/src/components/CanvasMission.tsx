import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, SkipBack } from "lucide-react";
import type { MissionPlan, SurfaceTelemetry } from "../types";

interface CanvasMissionProps {
  plan: MissionPlan;
}

function mapAzimuth(azimuth: number, width: number) {
  return ((azimuth % 360 + 360) % 360) / 360 * width;
}

export function CanvasMission({ plan }: CanvasMissionProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [seconds, setSeconds] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const phase = useMemo(() => plan.phases.find((item) => seconds >= item.start_seconds && seconds <= item.end_seconds) ?? plan.phases.at(-1)!, [plan.phases, seconds]);
  const telemetry: SurfaceTelemetry | undefined = useMemo(() => {
    const surface = plan.phases.find((item) => item.name === "SURFACE OPS");
    if (!surface || seconds < surface.start_seconds || !plan.surface_telemetry.length) return undefined;
    const ratio = (seconds - surface.start_seconds) / Math.max(1, surface.end_seconds - surface.start_seconds);
    return plan.surface_telemetry[Math.min(plan.surface_telemetry.length - 1, Math.round(ratio * (plan.surface_telemetry.length - 1)))];
  }, [plan.phases, plan.surface_telemetry, seconds]);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = window.setInterval(() => {
      setSeconds((current) => {
        const next = current + plan.duration_seconds / 600 * speed;
        if (next >= plan.duration_seconds) {
          setPlaying(false);
          return 0;
        }
        return next;
      });
    }, 100);
    return () => window.clearInterval(timer);
  }, [plan.duration_seconds, playing, speed]);

  useEffect(() => {
    setSeconds(0);
    setPlaying(false);
  }, [plan]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const context = canvas.getContext("2d");
    if (!context) return undefined;
    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const ratio = window.devicePixelRatio || 1;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      const ctx = context;
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#050914";
      ctx.fillRect(0, 0, width, height);
      for (let index = 0; index < 100; index += 1) {
        const x = ((index * 83 + 29) % 997) / 997 * width;
        const y = ((index * 47 + 13) % 389) / 389 * height;
        ctx.fillStyle = index % 9 === 0 ? "rgba(196,216,255,.68)" : "rgba(143,166,206,.35)";
        ctx.beginPath(); ctx.arc(x, y, index % 13 === 0 ? 1.4 : 0.75, 0, Math.PI * 2); ctx.fill();
      }
      ctx.strokeStyle = "rgba(139,163,204,.16)";
      ctx.lineWidth = 1;
      ctx.strokeRect(18, 16, width - 36, height - 32);

      if (telemetry) {
        drawSurfaceView(ctx, width, height, plan, telemetry);
      } else {
        drawTransitView(ctx, width, height, phase.name, seconds, phase.start_seconds, phase.end_seconds);
      }
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [phase, plan, seconds, telemetry]);

  const timeLabel = new Date(telemetry?.time_utc ?? new Date(new Date(plan.launch_utc).getTime() + seconds * 1000).toISOString()).toISOString().replace("T", " ").slice(0, 19) + " UTC";
  return <section className="panel simulator-panel">
    <div className="simulator-canvas-frame"><canvas ref={canvasRef} aria-label={`Illustrative mission animation, current phase ${phase.name}. Surface telemetry is displayed after landing.`} /><div className="canvas-corner canvas-corner-left"><span className="status-dot" />MISSION VISUALIZATION</div><div className="canvas-corner canvas-corner-right">{phase.illustrative ? "ILLUSTRATIVE TRAJECTORY" : "EPHEMERIS TELEMETRY"}</div></div>
    <div className="simulator-controls">
      <div className="sim-control-buttons">
        <button className="icon-button" onClick={() => { setSeconds(0); setPlaying(false); }} aria-label="Reset mission timeline"><SkipBack size={15} /></button>
        <button className="button button-primary play-button" onClick={() => setPlaying((active) => !active)}>{playing ? <Pause size={15} /> : <Play size={15} />}{playing ? "Pause" : "Play"}</button>
      </div>
      <label className="timeline-control"><span>Mission timeline</span><input type="range" min={0} max={plan.duration_seconds} step={Math.max(1, plan.duration_seconds / 1000)} value={seconds} onChange={(event) => { setPlaying(false); setSeconds(Number(event.target.value)); }} aria-label="Mission time scrubber" /><div className="timeline-labels"><span>Launch</span><span>{phase.name}</span><span>{timeLabel}</span></div></label>
      <label className="speed-control"><span>Playback</span><select value={speed} onChange={(event) => setSpeed(Number(event.target.value))} aria-label="Simulation playback speed">{[0.5, 1, 2, 4, 8].map((value) => <option key={value} value={value}>{value}×</option>)}</select></label>
    </div>
    <div className="phase-track" aria-label="Mission phase timeline">{plan.phases.map((item) => <div key={item.name} className={`phase-segment ${phase.name === item.name ? "phase-current" : ""}`} style={{ flexGrow: Math.max(0.03, item.end_seconds - item.start_seconds) }}><span>{item.name}</span></div>)}</div>
    <div className="sim-hud-grid">
      <div className="sim-hud-item"><span>MISSION PHASE</span><strong>{phase.name}</strong></div>
      <div className="sim-hud-item"><span>UTC</span><strong>{timeLabel}</strong></div>
      {telemetry ? <>
        <div className="sim-hud-item"><span>SUN ALTITUDE</span><strong className="value-sun">{telemetry.sun_alt_deg.toFixed(2)}° · {telemetry.sun_visible ? "VISIBLE" : "BELOW HORIZON"}</strong></div>
        <div className="sim-hud-item"><span>EARTH ALTITUDE</span><strong className="value-earth">{telemetry.earth_alt_deg.toFixed(2)}° · {telemetry.earth_visible ? "VISIBLE" : "BELOW HORIZON"}</strong></div>
      </> : <div className="sim-hud-item sim-hud-note"><span>SKY TELEMETRY</span><strong>Starts at landing; preceding scene is illustrative.</strong></div>}
    </div>
    <div className="simulator-note"><span className="footnote-marker">i</span><p>{plan.provenance.illustration_note} Surface Sun/Earth directions and visibility come from the Python mission plan.</p></div>
  </section>;
}

function drawTransitView(ctx: CanvasRenderingContext2D, width: number, height: number, phase: string, seconds: number, phaseStart: number, phaseEnd: number) {
  const sceneTop = 52;
  const centerY = height * 0.56;
  const earthX = width * 0.18;
  const moonX = width * 0.82;
  const moonRadius = Math.min(height * 0.13, 54);
  const ratio = Math.max(0, Math.min(1, (seconds - phaseStart) / Math.max(1, phaseEnd - phaseStart)));
  const rocket = phase === "LAUNCH" ? { x: earthX + 18 + ratio * 25, y: centerY - ratio * 90 } : phase === "TRANSIT" ? { x: earthX + (moonX - earthX) * ratio, y: centerY - Math.sin(ratio * Math.PI) * height * 0.22 } : phase === "LUNAR ORBIT" ? { x: moonX + Math.cos(ratio * Math.PI * 8) * (moonRadius + 35), y: centerY + Math.sin(ratio * Math.PI * 8) * (moonRadius + 35) } : phase === "POWERED DESCENT" ? { x: moonX - (moonRadius + 55) * (1 - ratio), y: centerY - (moonRadius + 70) * (1 - ratio) } : { x: moonX, y: centerY - moonRadius };

  ctx.font = "10px Inter, system-ui, sans-serif";
  ctx.fillStyle = "#75849e"; ctx.fillText("MISSION PHASE · SCHEMATIC VIEW", 34, sceneTop);
  ctx.strokeStyle = "rgba(122,156,209,.23)"; ctx.setLineDash([4, 7]); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(earthX + 26, centerY); ctx.quadraticCurveTo(width * 0.5, centerY - height * 0.36, moonX - moonRadius - 10, centerY); ctx.stroke(); ctx.setLineDash([]);

  const earthGradient = ctx.createRadialGradient(earthX - 8, centerY - 10, 2, earthX, centerY, 31);
  earthGradient.addColorStop(0, "#77c6ff"); earthGradient.addColorStop(1, "#174d84");
  ctx.fillStyle = earthGradient; ctx.beginPath(); ctx.arc(earthX, centerY, 28, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = "rgba(91,168,255,.25)"; ctx.beginPath(); ctx.arc(earthX, centerY, 37, 0, Math.PI * 2); ctx.stroke();
  const moonGradient = ctx.createRadialGradient(moonX - 18, centerY - 20, 5, moonX, centerY, moonRadius);
  moonGradient.addColorStop(0, "#dce4ef"); moonGradient.addColorStop(1, "#566276");
  ctx.fillStyle = moonGradient; ctx.beginPath(); ctx.arc(moonX, centerY, moonRadius, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = "rgba(47,58,78,.65)"; ctx.beginPath(); ctx.arc(moonX - 16, centerY + 8, moonRadius * 0.22, 0, Math.PI * 2); ctx.fill(); ctx.beginPath(); ctx.arc(moonX + 20, centerY - 14, moonRadius * 0.14, 0, Math.PI * 2); ctx.fill();

  if (phase === "LUNAR ORBIT") { ctx.strokeStyle = "rgba(211,221,238,.55)"; ctx.setLineDash([3, 5]); ctx.beginPath(); ctx.ellipse(moonX, centerY, moonRadius + 35, moonRadius + 22, 0, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); }
  if (phase === "POWERED DESCENT") { ctx.fillStyle = "rgba(245,184,75,.18)"; ctx.beginPath(); ctx.moveTo(rocket.x - 5, rocket.y + 7); ctx.lineTo(rocket.x + 5, rocket.y + 7); ctx.lineTo(rocket.x, rocket.y + 30); ctx.closePath(); ctx.fill(); }
  ctx.save(); ctx.translate(rocket.x, rocket.y); ctx.rotate(phase === "POWERED DESCENT" ? 0.35 : -0.45); ctx.fillStyle = "#f2f5fa"; ctx.beginPath(); ctx.moveTo(0, -9); ctx.lineTo(6, 7); ctx.lineTo(0, 4); ctx.lineTo(-6, 7); ctx.closePath(); ctx.fill(); ctx.restore();
  ctx.fillStyle = "#91a0b7"; ctx.textAlign = "center"; ctx.fillText("EARTH", earthX, centerY + 53); ctx.fillText("LUNAR SOUTH POLE", moonX, centerY + moonRadius + 23); ctx.textAlign = "left";
  ctx.fillStyle = "#b9c6d9"; ctx.font = "600 15px Inter, system-ui, sans-serif"; ctx.fillText(phase, 34, height - 42);
  ctx.fillStyle = "#687992"; ctx.font = "10px Inter, system-ui, sans-serif"; ctx.fillText("PHASE TIMING IS A DEMONSTRATION PROFILE · PATH GEOMETRY IS NOT A FLIGHT TRAJECTORY", 34, height - 24);
}

function drawSurfaceView(ctx: CanvasRenderingContext2D, width: number, height: number, plan: MissionPlan, sample: SurfaceTelemetry) {
  const margin = 38;
  const divider = width * 0.65;
  const top = 66;
  const plotBottom = height - 70;
  const plotHeight = plotBottom - top;
  const minAlt = -8;
  const maxAlt = 45;
  const yForAlt = (alt: number) => plotBottom - (Math.max(minAlt, Math.min(maxAlt, alt)) - minAlt) / (maxAlt - minAlt) * plotHeight;
  const profile = plan.horizon_profile;
  ctx.font = "10px Inter, system-ui, sans-serif"; ctx.fillStyle = "#8391a7";
  ctx.fillText("SURFACE HORIZON · AZIMUTH / ALTITUDE", margin, 42);
  ctx.fillText("LOCAL SKY RADAR", divider + 18, 42);

  ctx.fillStyle = "rgba(245,184,75,.08)"; ctx.fillRect(margin, top, divider - margin - 20, plotHeight);
  ctx.strokeStyle = "rgba(148,163,184,.12)"; ctx.lineWidth = 1;
  for (const altitude of [0, 15, 30, 45]) {
    const y = yForAlt(altitude); ctx.beginPath(); ctx.moveTo(margin, y); ctx.lineTo(divider - 20, y); ctx.stroke();
    ctx.fillStyle = "#6d7c93"; ctx.textAlign = "right"; ctx.fillText(`${altitude}°`, margin - 7, y + 3);
  }
  ctx.textAlign = "left";
  for (const azimuth of [0, 90, 180, 270, 360]) {
    const x = margin + azimuth / 360 * (divider - margin - 20); ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, plotBottom); ctx.stroke();
    ctx.fillStyle = "#6d7c93"; ctx.fillText(`${azimuth}°`, x - 9, plotBottom + 17);
  }
  ctx.beginPath(); ctx.moveTo(margin, yForAlt(0)); ctx.lineTo(divider - 20, yForAlt(0)); ctx.strokeStyle = "rgba(203,213,225,.55)"; ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
  ctx.beginPath();
  profile.azimuth_deg.forEach((az, index) => {
    const x = margin + mapAzimuth(az, divider - margin - 20);
    const y = yForAlt(profile.elevation_deg[index]);
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = profile.source === "dem" ? "#52d6a5" : "#f5b84b"; ctx.lineWidth = 1.7; ctx.stroke();
  const pointX = (az: number) => margin + mapAzimuth(az, divider - margin - 20);
  const pointY = (alt: number) => yForAlt(alt);
  drawSkyMarker(ctx, pointX(sample.sun_az_deg), pointY(sample.sun_alt_deg), "#f5b84b", "SUN", sample.sun_visible);
  drawSkyMarker(ctx, pointX(sample.earth_az_deg), pointY(sample.earth_alt_deg), "#5ba8ff", "EARTH", sample.earth_visible);
  ctx.fillStyle = "#9aa9bf"; ctx.font = "10px Inter, system-ui, sans-serif"; ctx.fillText(`HORIZON SOURCE · ${profile.source.toUpperCase()}`, margin, height - 30);

  const radarX = divider + (width - divider) * 0.52;
  const radarY = height * 0.54;
  const radius = Math.min((width - divider) * 0.34, height * 0.34);
  ctx.strokeStyle = "rgba(148,163,184,.2)"; ctx.lineWidth = 1;
  for (const r of [radius * 0.33, radius * 0.66, radius]) { ctx.beginPath(); ctx.arc(radarX, radarY, r, 0, Math.PI * 2); ctx.stroke(); }
  for (const degrees of [0, 90, 180, 270]) {
    const angle = (degrees - 90) * Math.PI / 180;
    ctx.beginPath(); ctx.moveTo(radarX, radarY); ctx.lineTo(radarX + Math.cos(angle) * radius, radarY + Math.sin(angle) * radius); ctx.stroke();
    ctx.fillStyle = "#78879e"; ctx.fillText(["N", "E", "S", "W"][degrees / 90], radarX + Math.cos(angle) * (radius + 12) - 3, radarY + Math.sin(angle) * (radius + 12) + 3);
  }
  drawRadarPoint(ctx, radarX, radarY, radius, sample.sun_az_deg, sample.sun_alt_deg, "#f5b84b", "SUN");
  drawRadarPoint(ctx, radarX, radarY, radius, sample.earth_az_deg, sample.earth_alt_deg, "#5ba8ff", "EARTH");
  ctx.fillStyle = "#a7b4c7"; ctx.textAlign = "center"; ctx.font = "10px Inter, system-ui, sans-serif";
  ctx.fillText(`SUN ${sample.sun_alt_deg.toFixed(1)}° ${sample.sun_visible ? "VISIBLE" : "BLOCKED"}`, radarX, height - 40);
  ctx.fillText(`EARTH ${sample.earth_alt_deg.toFixed(1)}° ${sample.earth_visible ? "VISIBLE" : "BLOCKED"}`, radarX, height - 23);
  ctx.textAlign = "left";
}

function drawSkyMarker(ctx: CanvasRenderingContext2D, x: number, y: number, color: string, label: string, visible: boolean) {
  ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
  ctx.strokeStyle = "#050914"; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = visible ? color : "#bac4d3"; ctx.font = "600 9px Inter, system-ui, sans-serif"; ctx.fillText(label, x + 7, y - 7);
}

function drawRadarPoint(ctx: CanvasRenderingContext2D, cx: number, cy: number, radius: number, azimuth: number, altitude: number, color: string, label: string) {
  const r = radius * (90 - Math.max(0, Math.min(90, altitude))) / 90;
  const angle = (azimuth - 90) * Math.PI / 180;
  const x = cx + Math.cos(angle) * r;
  const y = cy + Math.sin(angle) * r;
  ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
  ctx.fillStyle = color; ctx.font = "600 9px Inter, system-ui, sans-serif"; ctx.fillText(label, x + 7, y - 7);
}
