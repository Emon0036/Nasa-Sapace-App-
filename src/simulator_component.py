"""
Interactive HTML5/Canvas Mission Simulator Component.

Renders an ultra-fast, smooth 60 FPS client-side simulation of the complete
lunar mission: Earth Launch, Trans-Lunar Coast, Lunar Orbit Insertion,
Powered Descent to the South Pole, and Live Surface Operations (360° celestial radar,
panoramic astronaut terrain perspective, and real-time solar/comm telemetry).
"""

from __future__ import annotations

import json
from typing import Any, Dict


def get_simulator_html(plan_data: Dict[str, Any], height: int = 760) -> str:
    """Generate the self-contained HTML/CSS/JS string for the interactive simulator."""
    data_json = json.dumps(plan_data)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Lunar Horizon Mission Simulator</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      user-select: none;
    }}
    body {{
      background: #05070d;
      color: #e6ecff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      overflow: hidden;
      width: 100vw;
      height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    .sim-container {{
      display: flex;
      flex-direction: column;
      height: 100%;
      background: radial-gradient(circle at 50% 20%, #0d152c 0%, #05070d 80%);
      padding: 12px 16px;
      gap: 10px;
    }}
    /* Top Header HUD */
    .sim-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(14, 22, 45, 0.7);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(80, 110, 180, 0.25);
      border-radius: 10px;
      padding: 8px 16px;
      flex-shrink: 0;
    }}
    .sim-title-group {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .sim-badge {{
      background: #192548;
      color: #78a6ff;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid rgba(120, 166, 255, 0.3);
    }}
    .sim-phase-badge {{
      background: rgba(255, 184, 69, 0.15);
      color: #ffb845;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      padding: 4px 10px;
      border-radius: 6px;
      border: 1px solid rgba(255, 184, 69, 0.35);
      transition: all 0.3s ease;
    }}
    .sim-phase-badge.golden {{
      background: rgba(45, 212, 167, 0.2);
      color: #2dd4a7;
      border-color: #2dd4a7;
      box-shadow: 0 0 10px rgba(45, 212, 167, 0.3);
    }}
    .sim-telemetry-strip {{
      display: flex;
      align-items: center;
      gap: 20px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }}
    .telem-item {{
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }}
    .telem-label {{
      font-size: 9px;
      color: #7b8bad;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .telem-val {{
      font-weight: 600;
      color: #e6ecff;
    }}
    .telem-sub {{
      font-size: 10px;
      color: #7b8bad;
      font-weight: 400;
      margin-left: 4px;
      align-self: flex-end;
      margin-bottom: 1px;
    }}
    .val-sun {{ color: #ffb845; }}
    .val-earth {{ color: #4ea1ff; }}
    .val-gold {{ color: #2dd4a7; }}
    .val-alert {{ color: #ff6b8a; }}

    /* Main View Area */
    .sim-viewport {{
      flex: 1;
      display: flex;
      gap: 12px;
      position: relative;
      min-height: 0;
    }}
    .sim-canvas-block {{
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
      min-height: 0;
    }}
    .sim-canvas-wrapper {{
      flex: 1;
      position: relative;
      background: rgba(8, 12, 26, 0.85);
      border: 1px solid rgba(60, 85, 145, 0.3);
      border-radius: 12px;
      overflow: hidden;
      display: flex;
      box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.6);
    }}
    canvas {{
      display: block;
      width: 100%;
      height: 100%;
    }}

    /* Side Telemetry Panel */
    .sim-side-panel {{
      width: 280px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .gauge-card {{
      background: rgba(12, 18, 38, 0.75);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(80, 110, 180, 0.25);
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .gauge-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #97a3c7;
    }}
    .gauge-meter-bar {{
      height: 10px;
      background: rgba(25, 35, 65, 0.8);
      border-radius: 5px;
      overflow: hidden;
      position: relative;
      border: 1px solid rgba(70, 95, 155, 0.3);
    }}
    .gauge-fill {{
      height: 100%;
      width: 0%;
      border-radius: 5px;
      transition: width 0.1s linear, background-color 0.3s ease;
    }}
    .gauge-fill.sun {{
      background: linear-gradient(90deg, #ff9429, #ffc75f);
      box-shadow: 0 0 10px rgba(255, 184, 69, 0.5);
    }}
    .gauge-fill.earth {{
      background: linear-gradient(90deg, #2b7fff, #67b5ff);
      box-shadow: 0 0 10px rgba(78, 161, 255, 0.5);
    }}
    .gauge-status-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }}
    .status-pill {{
      font-size: 9px;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
      letter-spacing: 0.5px;
    }}
    .pill-active {{
      background: rgba(45, 212, 167, 0.2);
      color: #2dd4a7;
      border: 1px solid rgba(45, 212, 167, 0.4);
    }}
    .pill-blocked {{
      background: rgba(255, 107, 138, 0.2);
      color: #ff6b8a;
      border: 1px solid rgba(255, 107, 138, 0.4);
    }}

    .golden-banner {{
      background: linear-gradient(135deg, rgba(45, 212, 167, 0.15), rgba(78, 161, 255, 0.15));
      border: 1px solid rgba(45, 212, 167, 0.4);
      border-radius: 10px;
      padding: 10px 12px;
      text-align: center;
      font-size: 11px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .golden-title {{
      font-weight: 800;
      letter-spacing: 0.8px;
      color: #2dd4a7;
      text-transform: uppercase;
    }}
    .golden-sub {{
      font-size: 10px;
      color: #97a3c7;
    }}

    /* View Switcher Overlay */
    .view-mode-tabs {{
      position: absolute;
      top: 14px;
      right: 14px;
      display: flex;
      gap: 6px;
      background: rgba(10, 16, 35, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(80, 110, 180, 0.3);
      border-radius: 10px;
      padding: 6px;
      z-index: 10;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
    }}
    .view-btn {{
      background: transparent;
      color: #c2cee8;
      border: 1px solid transparent;
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
      text-align: left;
    }}
    .view-btn:hover {{
      color: #ffffff;
      background: rgba(120, 150, 220, 0.12);
      border-color: rgba(120, 150, 220, 0.3);
    }}
    .view-btn.active {{
      background: linear-gradient(135deg, rgba(43, 111, 229, 0.35), rgba(31, 76, 184, 0.25));
      color: #ffffff;
      border-color: rgba(120, 180, 255, 0.55);
      box-shadow: 0 4px 14px rgba(31, 76, 184, 0.35);
    }}
    .view-btn-icon {{
      font-size: 18px;
      line-height: 1;
      flex-shrink: 0;
      filter: drop-shadow(0 0 6px rgba(78, 161, 255, 0.5));
    }}
    .view-btn-stack {{
      display: flex;
      flex-direction: column;
      gap: 1px;
      min-width: 0;
      line-height: 1.2;
    }}
    .view-btn-title {{
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: #f0f4ff;
    }}
    .view-btn-sub {{
      font-size: 9px;
      color: #97a3c7;
      font-weight: 500;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }}
    .view-btn.active .view-btn-sub {{ color: #c9d4f0; }}

    /* Make the whole tab row wrap rather than overflow */
    .view-mode-tabs {{
      flex-wrap: wrap;
      max-width: 64%;
    }}

    /* Persistent canvas legend (top-left of canvas) */
    .canvas-legend {{
      position: absolute;
      top: 14px;
      left: 14px;
      background: rgba(8, 12, 26, 0.78);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(120, 160, 240, 0.32);
      border-radius: 10px;
      padding: 12px 14px;
      display: flex;
      flex-direction: column;
      gap: 5px;
      font-family: 'Space Grotesk', system-ui, sans-serif;
      font-size: 11px;
      color: #dde7ff;
      z-index: 10;
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
      min-width: 170px;
      letter-spacing: 0.02em;
    }}
    .canvas-legend::first-line {{ /* heading hint */ }}
    .legend-row {{
      display: flex;
      align-items: center;
      gap: 8px;
      letter-spacing: 0.02em;
    }}
    .legend-heading {{
      font-size: 9.5px;
      letter-spacing: 0.18em;
      color: #97a3c7;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 2px;
    }}
    .legend-swatch {{
      display: inline-block;
      width: 12px;
      height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: 0 0 6px currentColor;
    }}
    .legend-swatch.sun    {{ background: #ffb845; color: #ffb845; box-shadow: 0 0 10px #ffb845; }}
    .legend-swatch.earth  {{ background: #4ea1ff; color: #4ea1ff; box-shadow: 0 0 10px #4ea1ff; }}
    .legend-swatch.moon   {{ background: #d8e1ff; color: #d8e1ff; box-shadow: 0 0 8px #d8e1ff; }}
    .legend-swatch.rocket {{ background: #ff6b8a; color: #ff6b8a; box-shadow: 0 0 8px #ff6b8a; border-radius: 2px; transform: rotate(45deg); width: 9px; height: 9px; margin-left: 1.5px; margin-right: 1.5px; }}
    .legend-swatch.horizon{{ background: transparent; border: 1.5px dashed #9aa6c8; box-shadow: none; }}
    .legend-swatch.golden {{ background: #4ade80; color: #4ade80; box-shadow: 0 0 10px #4ade80; }}
    .legend-divider {{
      height: 1px;
      background: rgba(120, 160, 240, 0.25);
      margin: 4px 0 2px 0;
    }}

    /* Caption row under the canvas */
    .sim-caption {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      padding: 10px 14px;
      background: rgba(11, 16, 32, 0.55);
      border: 1px solid rgba(120, 150, 220, 0.22);
      border-top: 0;
      border-radius: 0 0 10px 10px;
      font-family: 'Space Grotesk', system-ui, sans-serif;
      font-size: 11px;
      color: #c2cee8;
    }}
    .sim-caption-item {{
      display: flex;
      align-items: flex-start;
      gap: 8px;
      line-height: 1.4;
    }}
    .sim-caption-item strong {{
      color: #ffffff;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      font-size: 9.5px;
      display: block;
      margin-bottom: 2px;
    }}

    /* Bottom Control Bar */
    .sim-controls {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      background: rgba(14, 22, 45, 0.85);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(80, 110, 180, 0.25);
      border-radius: 10px;
      padding: 10px 16px;
      flex-shrink: 0;
    }}
    .scrubber-row {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .timeline-slider {{
      flex: 1;
      -webkit-appearance: none;
      appearance: none;
      height: 6px;
      border-radius: 3px;
      background: #1b2648;
      outline: none;
      cursor: pointer;
    }}
    .timeline-slider::-webkit-slider-thumb {{
      -webkit-appearance: none;
      appearance: none;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #ffb845;
      border: 2px solid #ffffff;
      cursor: pointer;
      box-shadow: 0 0 10px rgba(255, 184, 69, 0.8);
      transition: transform 0.1s ease;
    }}
    .timeline-slider::-webkit-slider-thumb:hover {{
      transform: scale(1.25);
    }}
    .timeline-slider::-moz-range-thumb {{
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #ffb845;
      border: 2px solid #ffffff;
      cursor: pointer;
      box-shadow: 0 0 10px rgba(255, 184, 69, 0.8);
    }}
    .time-readout {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 11px;
      color: #97a3c7;
      min-width: 130px;
      text-align: right;
    }}
    .btn-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    .btn-group-left {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .ctrl-btn {{
      background: #1b284e;
      color: #e6ecff;
      border: 1px solid rgba(80, 115, 190, 0.4);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }}
    .ctrl-btn:hover {{
      background: #25396e;
      border-color: #6592e6;
    }}
    .ctrl-btn.primary {{
      background: linear-gradient(135deg, #2b6fe5, #1f4cb8);
      border-color: #6199ff;
    }}
    .ctrl-btn.primary:hover {{
      background: linear-gradient(135deg, #3c7eff, #285cdb);
    }}
    .ctrl-btn.nudge {{
      padding: 6px 10px;
      font-size: 13px;
      background: rgba(22, 32, 60, 0.55);
      color: #c9d4f0;
    }}
    .ctrl-btn.nudge:hover {{
      background: #25396e;
      color: #ffd07a;
    }}
    .phase-jumps {{
      display: flex;
      gap: 5px;
    }}
    .phase-btn {{
      background: rgba(22, 32, 60, 0.6);
      color: #8da0c7;
      border: 1px solid rgba(60, 85, 140, 0.3);
      padding: 4px 8px;
      border-radius: 5px;
      font-size: 10px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
    }}
    .phase-btn:hover {{
      color: #ffffff;
      background: #24355f;
    }}
    .phase-btn.active {{
      background: rgba(255, 184, 69, 0.2);
      color: #ffb845;
      border-color: rgba(255, 184, 69, 0.5);
    }}
    .speed-select {{
      background: #141d38;
      color: #e6ecff;
      border: 1px solid rgba(80, 115, 190, 0.4);
      padding: 5px 8px;
      border-radius: 6px;
      font-size: 11px;
      cursor: pointer;
      outline: none;
    }}
  </style>
</head>
<body>
  <div class="sim-container">
    <!-- Header HUD -->
    <div class="sim-header">
      <div class="sim-title-group">
        <span class="sim-badge" id="siteNameBadge">Site</span>
        <span class="sim-phase-badge" id="phaseBadge">SURFACE OPS</span>
      </div>
      <div class="sim-telemetry-strip">
        <div class="telem-item">
          <span class="telem-label">Mission Elapsed</span>
          <span class="telem-val" id="metVal">T+ 00:00:00</span>
          <span class="telem-val telem-sub" id="metTotalVal">/ T+ 00:00:00</span>
        </div>
        <div class="telem-item">
          <span class="telem-label">UTC Timestamp</span>
          <span class="telem-val" id="utcVal">2026-06-01 00:00</span>
        </div>
        <div class="telem-item">
          <span class="telem-label">Sun Elevation</span>
          <span class="telem-val val-sun" id="sunAltVal">+0.00°</span>
        </div>
        <div class="telem-item">
          <span class="telem-label">Earth Elevation</span>
          <span class="telem-val val-earth" id="earthAltVal">+0.00°</span>
        </div>
      </div>
    </div>

    <!-- Main Viewport Area -->
    <div class="sim-viewport">
      <div class="sim-canvas-block">
      <div class="sim-canvas-wrapper" id="canvasWrapper">
        <div class="view-mode-tabs" id="viewModeTabs">
          <button class="view-btn active" data-view="split">
            <span class="view-btn-icon">🔀</span>
            <span class="view-btn-stack">
              <span class="view-btn-title">Split View</span>
              <span class="view-btn-sub">Sky radar + astronaut ground</span>
            </span>
          </button>
          <button class="view-btn" data-view="radar">
            <span class="view-btn-icon">🎯</span>
            <span class="view-btn-stack">
              <span class="view-btn-title">360° Sky Radar</span>
              <span class="view-btn-sub">Polar view of Sun and Earth</span>
            </span>
          </button>
          <button class="view-btn" data-view="horizon">
            <span class="view-btn-icon">🌄</span>
            <span class="view-btn-stack">
              <span class="view-btn-title">Astronaut Ground View</span>
              <span class="view-btn-sub">180° panorama from the lander</span>
            </span>
          </button>
          <button class="view-btn" data-view="orbit">
            <span class="view-btn-icon">🚀</span>
            <span class="view-btn-stack">
              <span class="view-btn-title">Flight Trajectory</span>
              <span class="view-btn-sub">Earth → Moon, top-down</span>
            </span>
          </button>
        </div>

        <!-- Persistent legend: always visible, top-left of canvas -->
        <div class="canvas-legend">
          <div class="legend-heading">LEGEND</div>
          <div class="legend-row"><span class="legend-swatch sun"></span><span>Sun</span></div>
          <div class="legend-row"><span class="legend-swatch earth"></span><span>Earth</span></div>
          <div class="legend-row"><span class="legend-swatch moon"></span><span>Moon</span></div>
          <div class="legend-row"><span class="legend-swatch rocket"></span><span>Rocket / Spacecraft</span></div>
          <div class="legend-divider"></div>
          <div class="legend-row"><span class="legend-swatch horizon"></span><span>Terrain horizon</span></div>
          <div class="legend-row"><span class="legend-swatch golden"></span><span>Golden window</span></div>
        </div>

        <canvas id="simCanvas"></canvas>
      </div>

      <!-- "How to read this view" caption row -->
      <div class="sim-caption">
        <div class="sim-caption-item">
          <span style="font-size:18px; line-height:1">🎯</span>
          <span><strong>Radar rings</strong>Concentric rings = altitude (0° at horizon, 90° overhead). The dashed line is the terrain horizon — anything below it is occluded.</span>
        </div>
        <div class="sim-caption-item">
          <span style="font-size:18px; line-height:1">☀🌐</span>
          <span><strong>Bodies</strong>Gold = Sun, blue = Earth. They appear at their real azimuth and elevation for the current time. Click a view button above to focus.</span>
        </div>
        <div class="sim-caption-item">
          <span style="font-size:18px; line-height:1">✦</span>
          <span><strong>Golden Window</strong>A pulsing green ring appears when the Sun AND Earth are both above the terrain. That's your mission window.</span>
        </div>
      </div>
      </div>

      <!-- Side Gauges & Engineering Status -->
      <div class="sim-side-panel">
        <!-- Solar Power Gauge -->
        <div class="gauge-card">
          <div class="gauge-header">
            <span>Solar Power</span>
            <span id="powerPctText" class="val-sun" style="font-size:13px">0%</span>
          </div>
          <div class="gauge-meter-bar">
            <div class="gauge-fill sun" id="powerFill"></div>
          </div>
          <div class="gauge-status-row">
            <span id="powerStatusPill" class="status-pill pill-blocked">SHADOWED</span>
            <span style="font-size:10px; color:#8fa0c9">Clearance: <b id="sunClearText" class="val-sun">+0.0°</b></span>
          </div>
        </div>

        <!-- Earth DTE Comm Gauge -->
        <div class="gauge-card">
          <div class="gauge-header">
            <span>Direct-To-Earth Comm</span>
            <span id="commPctText" class="val-earth" style="font-size:13px">0%</span>
          </div>
          <div class="gauge-meter-bar">
            <div class="gauge-fill earth" id="commFill"></div>
          </div>
          <div class="gauge-status-row">
            <span id="commStatusPill" class="status-pill pill-blocked">LOS BLOCKED</span>
            <span style="font-size:10px; color:#8fa0c9">Clearance: <b id="earthClearText" class="val-earth">+0.0°</b></span>
          </div>
        </div>

        <!-- Golden Window Banner -->
        <div class="golden-banner" id="goldenBanner">
          <div class="golden-title" id="goldenTitle">INACTIVE</div>
          <div class="golden-sub" id="goldenSub">Requires simultaneous solar power and direct line-of-sight to Earth.</div>
        </div>

        <!-- Coordinates Summary -->
        <div class="gauge-card" style="font-size:11px;">
          <div class="gauge-header" style="margin-bottom:2px">
            <span>Selenographic Coordinates</span>
          </div>
          <div style="display:flex; justify-content:space-between; color:#8da2cf;">
            <span>Latitude</span>
            <b id="siteLatText" style="color:#e6ecff">-89.45° S</b>
          </div>
          <div style="display:flex; justify-content:space-between; color:#8da2cf;">
            <span>Longitude</span>
            <b id="siteLonText" style="color:#e6ecff">160.0° E</b>
          </div>
          <div style="display:flex; justify-content:space-between; color:#8da2cf;">
            <span>Elevation</span>
            <b id="siteElevText" style="color:#e6ecff">1450 m</b>
          </div>
        </div>
      </div>
    </div>

    <!-- Playback Control Bar -->
    <div class="sim-controls">
      <div class="scrubber-row">
        <input type="range" class="timeline-slider" id="timeSlider" min="0" max="1000" value="700" step="1">
        <span class="time-readout" id="timeReadout">Day 3.5 / 8.0</span>
      </div>
      <div class="btn-row">
        <div class="btn-group-left">
          <button class="ctrl-btn primary" id="playBtn">▶ Play</button>
          <button class="ctrl-btn" id="resetBtn">⏮ Reset</button>
          <button class="ctrl-btn nudge" id="nudgeBackBtn" title="Step back 5%">⏪</button>
          <button class="ctrl-btn nudge" id="nudgeFwdBtn" title="Step forward 5%">⏩</button>
          <select class="speed-select" id="speedSelect">
            <option value="1">1x Realtime</option>
            <option value="5">5x Speed</option>
            <option value="15" selected>15x Speed</option>
            <option value="60">60x Speed</option>
            <option value="200">200x Fast Sweep</option>
          </select>
        </div>

        <!-- Quick Phase Selector Buttons -->
        <div class="phase-jumps">
          <button class="phase-btn" data-time="0">Launch</button>
          <button class="phase-btn" data-time="0.1">Transit</button>
          <button class="phase-btn" data-time="0.48">Orbit</button>
          <button class="phase-btn" data-time="0.52">Descent</button>
          <button class="phase-btn active" data-time="0.6">Surface</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    // Injected mission plan dataset
    const plan = {data_json};

    // State
    let isPlaying = false;
    let speed = 15;
    let currentTimeSec = (plan.launch_seconds + plan.transit_seconds + plan.orbit_seconds + plan.descent_seconds); // Start in surface ops by default
    let activeView = "split"; // 'radar', 'horizon', 'split', 'orbit'
    let lastTimestamp = 0;

    // Elements
    const canvas = document.getElementById("simCanvas");
    const ctx = canvas.getContext("2d");
    const playBtn = document.getElementById("playBtn");
    const resetBtn = document.getElementById("resetBtn");
    const timeSlider = document.getElementById("timeSlider");
    const speedSelect = document.getElementById("speedSelect");
    const siteNameBadge = document.getElementById("siteNameBadge");
    const phaseBadge = document.getElementById("phaseBadge");
    const metVal = document.getElementById("metVal");
    const utcVal = document.getElementById("utcVal");
    const sunAltVal = document.getElementById("sunAltVal");
    const earthAltVal = document.getElementById("earthAltVal");
    const powerPctText = document.getElementById("powerPctText");
    const powerFill = document.getElementById("powerFill");
    const powerStatusPill = document.getElementById("powerStatusPill");
    const sunClearText = document.getElementById("sunClearText");
    const commPctText = document.getElementById("commPctText");
    const commFill = document.getElementById("commFill");
    const commStatusPill = document.getElementById("commStatusPill");
    const earthClearText = document.getElementById("earthClearText");
    const goldenBanner = document.getElementById("goldenBanner");
    const goldenTitle = document.getElementById("goldenTitle");
    const goldenSub = document.getElementById("goldenSub");
    const siteLatText = document.getElementById("siteLatText");
    const siteLonText = document.getElementById("siteLonText");
    const siteElevText = document.getElementById("siteElevText");
    const timeReadout = document.getElementById("timeReadout");

    // Initialize Site Metadata
    siteNameBadge.textContent = plan.site.name;
    siteLatText.textContent = plan.site.lat.toFixed(2) + "°";
    siteLonText.textContent = plan.site.lon.toFixed(1) + "°";
    siteElevText.textContent = plan.site.elev_m.toFixed(0) + " m";

    // Setup Canvas Resolution
    function resizeCanvas() {{
      const rect = canvas.parentElement.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
    }}
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();

    // Starfield Cache
    const stars = [];
    for (let i = 0; i < 160; i++) {{
      stars.push({{
        x: Math.random(),
        y: Math.random(),
        size: Math.random() * 1.8 + 0.6,
        baseAlpha: Math.random() * 0.7 + 0.3,
        phase: Math.random() * Math.PI * 2,
        speed: 0.6 + Math.random() * 1.4
      }});
    }}

    // A shared millisecond clock used by all twinkle / pulse animations so
    // they stay phase-locked across the radar, ground view, and trajectory.
    function clockMs() {{ return performance.now(); }}

    // Draw a body (Sun / Earth / Moon / Rocket) with a clear in-canvas label.
    // `dotDx/dotDy` lets the caller offset the label off-center so it
    // doesn't sit on top of the body itself.
    function drawLabeledBody(x, y, radius, label, color, {{
      labelDx = 0, labelDy = -radius - 12, fontSize = 12, halo = true
    }} = {{}}) {{
      // Pill background for the label
      ctx.save();
      ctx.font = `bold ${{fontSize}}px 'Space Grotesk', system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const tw = ctx.measureText(label).width;
      const padX = 8, padY = 4;
      const lx = x + labelDx;
      const ly = y + labelDy;
      if (halo) {{
        ctx.fillStyle = "rgba(8, 12, 26, 0.78)";
        const w = tw + padX * 2;
        const h = fontSize + padY * 2;
        const r = h / 2;
        ctx.beginPath();
        if (ctx.roundRect) {{
          ctx.roundRect(lx - w / 2, ly - h / 2, w, h, r);
        }} else {{
          ctx.rect(lx - w / 2, ly - h / 2, w, h);
        }}
        ctx.fill();
        // Outline
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.globalAlpha = 0.55;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }}
      // Label text
      ctx.fillStyle = color;
      ctx.fillText(label, lx, ly);
      ctx.restore();
    }}

    // Phase Calculation
    function getPhase(t) {{
      if (t < plan.launch_seconds) return "LAUNCH";
      if (t < plan.launch_seconds + plan.transit_seconds) return "TRANSIT";
      const tOrbit = t - plan.launch_seconds - plan.transit_seconds;
      if (tOrbit < plan.orbit_seconds) return "LUNAR ORBIT";
      const tDesc = tOrbit - plan.orbit_seconds;
      if (tDesc < plan.descent_seconds) return "POWERED DESCENT";
      return "SURFACE OPS";
    }}

    // Time Formatting
    function formatMET(t) {{
      const d = Math.floor(t / 86400);
      const h = Math.floor((t % 86400) / 3600);
      const m = Math.floor((t % 3600) / 60);
      const s = Math.floor(t % 60);
      return `T+${{d}}d ${{String(h).padStart(2, "0")}}:${{String(m).padStart(2, "0")}}:${{String(s).padStart(2, "0")}}`;
    }}

    // Surface Data Interpolation
    function getSurfaceTelemetry(t) {{
      const surfT = t - (plan.launch_seconds + plan.transit_seconds + plan.orbit_seconds + plan.descent_seconds);
      if (surfT < 0 || !plan.surface.sun_alt.length) {{
        return {{
          sunAlt: 0, sunAz: 0, earthAlt: 0, earthAz: 0,
          hSun: 0, hEarth: 0, sunVis: false, earthVis: false,
          power: 0, comm: 0, timeStr: plan.launch_utc
        }};
      }}
      const frac = Math.min(1, Math.max(0, surfT / plan.surface_seconds));
      const idxF = frac * (plan.surface.sun_alt.length - 1);
      const i0 = Math.floor(idxF);
      const i1 = Math.min(plan.surface.sun_alt.length - 1, i0 + 1);
      const w = idxF - i0;

      const sunAlt = plan.surface.sun_alt[i0] * (1 - w) + plan.surface.sun_alt[i1] * w;
      const sunAz = plan.surface.sun_az[i0] * (1 - w) + plan.surface.sun_az[i1] * w;
      const earthAlt = plan.surface.earth_alt[i0] * (1 - w) + plan.surface.earth_alt[i1] * w;
      const earthAz = plan.surface.earth_az[i0] * (1 - w) + plan.surface.earth_az[i1] * w;
      const hSun = plan.surface.horizon_sun[i0] * (1 - w) + plan.surface.horizon_sun[i1] * w;
      const hEarth = plan.surface.horizon_earth[i0] * (1 - w) + plan.surface.horizon_earth[i1] * w;

      const sunVis = sunAlt > hSun;
      const earthVis = earthAlt > hEarth;
      // Solar power scaling: non-zero only when sun is up, higher altitude gives stronger irradiance
      const power = sunVis ? Math.min(100, Math.max(10, Math.sin(Math.max(0.1, sunAlt) * Math.PI / 180) * 1200 + 40)) : 0;
      const comm = earthVis ? Math.min(100, Math.max(20, (earthAlt - hEarth) * 20 + 30)) : 0;

      return {{
        sunAlt, sunAz, earthAlt, earthAz,
        hSun, hEarth, sunVis, earthVis,
        power, comm, timeStr: plan.surface.times[i0]
      }};
    }}

    // Main Draw Loop
    function render(now) {{
      if (!lastTimestamp) lastTimestamp = now;
      const dt = (now - lastTimestamp) / 1000;
      lastTimestamp = now;

      if (isPlaying) {{
        // Scale speed: 1x = 1 mission sec per real sec. 15x = 15 mission sec / real sec
        // During surface ops, scale so 1 full lunar day passes in ~40 seconds at 15x
        const advance = dt * speed * 200;
        currentTimeSec = (currentTimeSec + advance) % plan.total_seconds;
        timeSlider.value = (currentTimeSec / plan.total_seconds) * 1000;
      }}

      const phase = getPhase(currentTimeSec);
      const telem = getSurfaceTelemetry(currentTimeSec);

      // Update UI Telemetry Readouts
      updateTelemetryUI(phase, telem);

      // Clear Canvas
      const w = canvas.parentElement.clientWidth;
      const h = canvas.parentElement.clientHeight;
      ctx.clearRect(0, 0, w, h);

      // Draw Background Stars
      drawStarfield(w, h);

      // Determine Which Canvas View to Render
      if (phase !== "SURFACE OPS" && activeView !== "radar" && activeView !== "horizon" && activeView !== "split") {{
        drawTrajectoryView(w, h, phase, currentTimeSec);
      }} else {{
        if (activeView === "radar") {{
          drawRadarView(w / 2, h / 2, Math.min(w, h) * 0.44, telem);
        }} else if (activeView === "horizon") {{
          drawHorizonView(0, 0, w, h, telem);
        }} else if (activeView === "split") {{
          // Split screen
          const halfW = w / 2;
          drawRadarView(halfW / 2, h / 2, Math.min(halfW, h) * 0.44, telem);
          ctx.save();
          ctx.beginPath();
          ctx.rect(halfW, 0, halfW, h);
          ctx.clip();
          drawHorizonView(halfW, 0, halfW, h, telem);
          ctx.restore();
          // Divider line — gold-tinted gradient when in a golden window
          const gold = telem.sunVis && telem.earthVis;
          ctx.lineWidth = gold ? 3 : 1;
          const dividerGrad = ctx.createLinearGradient(halfW, 0, halfW, h);
          if (gold) {{
            dividerGrad.addColorStop(0, "rgba(74, 222, 128, 0.0)");
            dividerGrad.addColorStop(0.5, "rgba(74, 222, 128, 0.65)");
            dividerGrad.addColorStop(1.0, "rgba(74, 222, 128, 0.0)");
          }} else {{
            dividerGrad.addColorStop(0, "rgba(70, 95, 160, 0.0)");
            dividerGrad.addColorStop(0.5, "rgba(70, 95, 160, 0.5)");
            dividerGrad.addColorStop(1, "rgba(70, 95, 160, 0.0)");
          }}
          ctx.strokeStyle = dividerGrad;
          ctx.beginPath();
          ctx.moveTo(halfW, 0); ctx.lineTo(halfW, h);
          ctx.stroke();
        }} else {{
          drawTrajectoryView(w, h, phase, currentTimeSec);
        }}
      }}

      requestAnimationFrame(render);
    }}

    // Starfield (twinkles in sync across all views)
    function drawStarfield(w, h) {{
      const now = clockMs() / 1000.0;
      for (const s of stars) {{
        const twinkle = 0.55 + 0.45 * Math.sin(now * s.speed + s.phase);
        const a = Math.max(0.05, Math.min(1.0, s.baseAlpha * twinkle));
        ctx.fillStyle = `rgba(220, 235, 255, ${{a.toFixed(3)}})`;
        ctx.beginPath();
        ctx.arc(s.x * w, s.y * h, s.size, 0, Math.PI * 2);
        ctx.fill();
        // Occasional faint streak on the largest stars for motion feel
        if (s.size > 1.6) {{
          ctx.strokeStyle = `rgba(220, 235, 255, ${{(a * 0.25).toFixed(3)}})`;
          ctx.lineWidth = 0.6;
          ctx.beginPath();
          ctx.moveTo(s.x * w - s.size * 4, s.y * h);
          ctx.lineTo(s.x * w + s.size * 4, s.y * h);
          ctx.stroke();
        }}
      }}
    }}

    // View: 360° Celestial Polar Sky Radar
    function drawRadarView(cx, cy, radius, telem) {{
      ctx.save();

      // Outer Glow & Circle
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      grad.addColorStop(0, "rgba(10, 18, 40, 0.4)");
      grad.addColorStop(1, "rgba(5, 8, 20, 0.95)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Concentric Elevation Grid Rings (0°, 30°, 60°)
      // Thicker dot-dash ring style for an antialiased feel that visually
      // subscribes to the dashboard's "instrument" aesthetic.
      ctx.strokeStyle = "rgba(120, 150, 220, 0.18)";
      ctx.lineWidth = 1.2;
      [0.333, 0.666, 1.0].forEach((f, i) => {{
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.arc(cx, cy, radius * f, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(140, 165, 220, 0.5)";
        ctx.font = "10px ui-monospace, monospace";
        ctx.fillText(`${{Math.round(90 - f * 90)}}°`, cx + 6, cy - radius * f + 12);
      }});

      // Compass Crosshairs (N, E, S, W)
      ctx.strokeStyle = "rgba(120, 150, 220, 0.22)";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(cx, cy - radius); ctx.lineTo(cx, cy + radius);
      ctx.moveTo(cx - radius, cy); ctx.lineTo(cx + radius, cy);
      ctx.stroke();
      ctx.setLineDash([]);

      // Cardinal Labels with subtle drop-shadow for legibility
      ctx.save();
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const cardinals = [
        ["N (0°)",   cx,                 cy - radius + 14],
        ["S (180°)", cx,                 cy + radius - 14],
        ["E (90°)",  cx + radius - 24,   cy],
        ["W (270°)", cx - radius + 24,   cy],
      ];
      for (const [t, x, y] of cardinals) {{
        ctx.fillStyle = "rgba(8, 12, 26, 0.9)";
        ctx.fillText(t, x + 1, y + 1);
        ctx.fillStyle = "#a8bce8";
        ctx.fillText(t, x, y);
      }}
      ctx.restore();

      // Draw Local Terrain Horizon Mask Polygon
      const profAz = plan.horizon_profile.azimuth_deg;
      const profEl = plan.horizon_profile.elevation_deg;
      if (profAz && profAz.length) {{
        ctx.beginPath();
        for (let i = 0; i < profAz.length; i++) {{
          const theta = (profAz[i] - 90) * Math.PI / 180; // North = -90 deg (Up)
          const el = profEl[i];
          const r = radius * ((90 - el) / 90);
          const px = cx + r * Math.cos(theta);
          const py = cy + r * Math.sin(theta);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }}
        ctx.closePath();
        ctx.strokeStyle = "rgba(160, 185, 255, 0.65)";
        ctx.setLineDash([4, 3]);
        ctx.lineWidth = 1.8;
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "rgba(80, 120, 210, 0.08)";
        ctx.fill();
      }}

      // Helper for polar coords
      function getBodyCoords(az, alt) {{
        const theta = (az - 90) * Math.PI / 180;
        const clampedAlt = Math.max(-10, Math.min(90, alt));
        const r = radius * ((90 - clampedAlt) / 90);
        return {{
          x: cx + r * Math.cos(theta),
          y: cy + r * Math.sin(theta)
        }};
      }}

      // Draw Sun
      const sunPos = getBodyCoords(telem.sunAz, telem.sunAlt);
      // Ray line from center to sun
      ctx.strokeStyle = telem.sunVis ? "rgba(255, 184, 69, 0.3)" : "rgba(255, 184, 69, 0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx, cy); ctx.lineTo(sunPos.x, sunPos.y);
      ctx.stroke();

      // Sun Glow
      if (telem.sunVis) {{
        const sunGlow = ctx.createRadialGradient(sunPos.x, sunPos.y, 2, sunPos.x, sunPos.y, 22);
        sunGlow.addColorStop(0, "rgba(255, 200, 80, 0.9)");
        sunGlow.addColorStop(0.4, "rgba(255, 170, 40, 0.4)");
        sunGlow.addColorStop(1, "rgba(255, 150, 0, 0)");
        ctx.fillStyle = sunGlow;
        ctx.beginPath();
        ctx.arc(sunPos.x, sunPos.y, 22, 0, Math.PI * 2);
        ctx.fill();
      }}
      // Sun Disc
      ctx.fillStyle = telem.sunVis ? "#ffb845" : "#6a5024";
      ctx.beginPath();
      ctx.arc(sunPos.x, sunPos.y, telem.sunVis ? 7 : 5, 0, Math.PI * 2);
      ctx.fill();
      // Sun label pill (below the disc, well clear of horizon line)
      drawLabeledBody(sunPos.x, sunPos.y, 7,
        telem.sunVis ? "☀ SUN (visible)" : "☀ SUN (below horizon)",
        "#ffb845", {{ labelDx: 0, labelDy: 18, fontSize: 11, halo: true }});

      // Draw Earth
      const earthPos = getBodyCoords(telem.earthAz, telem.earthAlt);
      // Comm Beam to Center
      ctx.strokeStyle = telem.earthVis ? "rgba(78, 161, 255, 0.4)" : "rgba(255, 107, 138, 0.2)";
      ctx.lineWidth = telem.earthVis ? 1.5 : 1;
      ctx.setLineDash(telem.earthVis ? [] : [3, 3]);
      ctx.beginPath();
      ctx.moveTo(cx, cy); ctx.lineTo(earthPos.x, earthPos.y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Earth Glow
      if (telem.earthVis) {{
        const earthGlow = ctx.createRadialGradient(earthPos.x, earthPos.y, 2, earthPos.x, earthPos.y, 20);
        earthGlow.addColorStop(0, "rgba(100, 180, 255, 0.8)");
        earthGlow.addColorStop(0.5, "rgba(60, 130, 255, 0.3)");
        earthGlow.addColorStop(1, "rgba(30, 80, 220, 0)");
        ctx.fillStyle = earthGlow;
        ctx.beginPath();
        ctx.arc(earthPos.x, earthPos.y, 20, 0, Math.PI * 2);
        ctx.fill();
      }}
      // Earth Disc
      ctx.fillStyle = telem.earthVis ? "#4ea1ff" : "#1e3b66";
      ctx.beginPath();
      ctx.arc(earthPos.x, earthPos.y, telem.earthVis ? 8 : 5, 0, Math.PI * 2);
      ctx.fill();
      // Earth label pill
      drawLabeledBody(earthPos.x, earthPos.y, 8,
        telem.earthVis ? "🌐 EARTH (visible)" : "🌐 EARTH (below horizon)",
        "#4ea1ff", {{ labelDx: 0, labelDy: 18, fontSize: 11, halo: true }});

      // Center Lander / Rocket marker
      ctx.fillStyle = "#ff6b8a";
      ctx.beginPath();
      ctx.arc(cx, cy, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.stroke();
      drawLabeledBody(cx, cy, 4, "🚀 YOU", "#ff6b8a",
        {{ labelDx: 0, labelDy: -14, fontSize: 10, halo: true }});

      // Golden Window Pulse — soft pulsing green ring when both Sun and
      // Earth are above the terrain horizon at the current time.
      if (telem.sunVis && telem.earthVis) {{
        const pulse = 0.5 + 0.5 * Math.sin(clockMs() / 600);
        const pulseAlpha = 0.18 + 0.32 * pulse;
        const pulseR = radius * 0.86 + pulse * radius * 0.04;
        ctx.strokeStyle = `rgba(74, 222, 128, ${{pulseAlpha.toFixed(3)}})`;
        ctx.lineWidth = 3 + pulse * 2;
        ctx.setLineDash([10, 6]);
        ctx.beginPath();
        ctx.arc(cx, cy, pulseR, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        // "GOLDEN WINDOW" label
        ctx.save();
        ctx.font = "bold 11px sans-serif";
        ctx.fillStyle = `rgba(74, 222, 128, ${{(0.7 + 0.3 * pulse).toFixed(3)}})`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.shadowColor = "rgba(74, 222, 128, 0.8)";
        ctx.shadowBlur = 10;
        ctx.fillText("✦ GOLDEN WINDOW", cx, cy - radius * 0.55);
        ctx.restore();
      }}

      ctx.restore();
    }}

    // View: Panoramic Astronaut Ground Perspective
    function drawHorizonView(ox, oy, w, h, telem) {{
      ctx.save();

      // Sky gradient
      const skyGrad = ctx.createLinearGradient(ox, oy, ox, oy + h);
      skyGrad.addColorStop(0, "#05070f");
      skyGrad.addColorStop(0.7, "#0c152a");
      skyGrad.addColorStop(1, "#18223d");
      ctx.fillStyle = skyGrad;
      ctx.fillRect(ox, oy, w, h);

      // Horizon line calculation: 0 deg altitude is at 60% height
      const zeroY = oy + h * 0.60;
      const degScale = (h * 0.35) / 10.0; // 10 deg above horizon spans 35% height

      // Panoramic terrain profile: map azimuth -90 to +90 deg relative to astronaut view
      const heading = telem.sunAz; // Face Sun by default for dramatic lighting
      const profAz = plan.horizon_profile.azimuth_deg;
      const profEl = plan.horizon_profile.elevation_deg;

      // Draw Sun
      const relSunAz = ((telem.sunAz - heading + 540) % 360) - 180;
      const sunPx = ox + w * 0.5 + (relSunAz / 90.0) * (w * 0.5);
      const sunPy = zeroY - telem.sunAlt * degScale;

      if (telem.sunVis) {{
        // Sun radiant corona
        const sGrad = ctx.createRadialGradient(sunPx, sunPy, 4, sunPx, sunPy, 60);
        sGrad.addColorStop(0, "rgba(255, 230, 140, 1.0)");
        sGrad.addColorStop(0.2, "rgba(255, 180, 50, 0.6)");
        sGrad.addColorStop(0.6, "rgba(255, 140, 20, 0.2)");
        sGrad.addColorStop(1, "rgba(255, 100, 0, 0)");
        ctx.fillStyle = sGrad;
        ctx.beginPath();
        ctx.arc(sunPx, sunPy, 60, 0, Math.PI * 2);
        ctx.fill();
      }}
      ctx.fillStyle = telem.sunVis ? "#fff2c4" : "#6a5223";
      ctx.beginPath();
      ctx.arc(sunPx, sunPy, 14, 0, Math.PI * 2);
      ctx.fill();
      // Sun label pill in the panorama
      drawLabeledBody(sunPx, sunPy, 14,
        telem.sunVis ? "☀ SUN" : "☀ SUN (below ridge)",
        "#ffb845", {{ labelDx: 0, labelDy: -22, fontSize: 12, halo: true }});

      // Draw Earth
      const relEarthAz = ((telem.earthAz - heading + 540) % 360) - 180;
      const earthPx = ox + w * 0.5 + (relEarthAz / 90.0) * (w * 0.5);
      const earthPy = zeroY - telem.earthAlt * degScale;

      if (telem.earthVis) {{
        const eGrad = ctx.createRadialGradient(earthPx, earthPy, 4, earthPx, earthPy, 40);
        eGrad.addColorStop(0, "rgba(120, 190, 255, 0.9)");
        eGrad.addColorStop(0.4, "rgba(60, 130, 255, 0.4)");
        eGrad.addColorStop(1, "rgba(30, 70, 200, 0)");
        ctx.fillStyle = eGrad;
        ctx.beginPath();
        ctx.arc(earthPx, earthPy, 40, 0, Math.PI * 2);
        ctx.fill();
      }}
      ctx.fillStyle = telem.earthVis ? "#4ea1ff" : "#1a3459";
      ctx.beginPath();
      ctx.arc(earthPx, earthPy, 12, 0, Math.PI * 2);
      ctx.fill();
      // Earth label pill in the panorama
      drawLabeledBody(earthPx, earthPy, 12,
        telem.earthVis ? "🌐 EARTH" : "🌐 EARTH (below ridge)",
        "#4ea1ff", {{ labelDx: 0, labelDy: -22, fontSize: 12, halo: true }});

      // Draw Mountainous Lunar Terrain Silhouette
      ctx.beginPath();
      ctx.moveTo(ox, oy + h);
      ctx.lineTo(ox, zeroY);

      const nSteps = 120;
      for (let i = 0; i <= nSteps; i++) {{
        const frac = i / nSteps;
        const viewAz = (heading - 90 + frac * 180 + 360) % 360;
        // Interpolate profile elevation at viewAz
        const idx = Math.floor(viewAz);
        const el = profEl[idx % profEl.length] || 0.5;
        const px = ox + frac * w;
        const py = zeroY - el * degScale;
        ctx.lineTo(px, py);
      }}

      ctx.lineTo(ox + w, zeroY);
      ctx.lineTo(ox + w, oy + h);
      ctx.closePath();

      // Terrain fill
      const terrainGrad = ctx.createLinearGradient(ox, zeroY - 20, ox, oy + h);
      terrainGrad.addColorStop(0, "#161c2d");
      terrainGrad.addColorStop(0.3, "#0e1320");
      terrainGrad.addColorStop(1, "#070912");
      ctx.fillStyle = terrainGrad;
      ctx.fill();

      // Lit-terrain half overlay: terrain pixels whose azimuth lies within
      // ±90° of the Sun's azimuth get a warm, transparent overlay to simulate
      // sunlight pouring along the ridge. Cheap (one clipped fill) and
      // visually rich.
      if (telem.sunVis && telem.sunAlt > -1.5) {{
        const sunHalfRel = Math.max(-90, Math.min(90, relSunAz));
        const splitX = ox + w * 0.5 + (sunHalfRel / 90.0) * (w * 0.5);
        ctx.save();
        ctx.beginPath();
        ctx.rect(Math.min(ox + 0.0, splitX), zeroY - 40, Math.abs(splitX - (ox + w * 0.5 + 90 * w * 0.5 / 90)), h);
        ctx.clip();
        const litGrad = ctx.createLinearGradient(0, zeroY - 20, 0, oy + h);
        litGrad.addColorStop(0, "rgba(255, 184, 69, 0.18)");
        litGrad.addColorStop(0.4, "rgba(255, 140, 40, 0.08)");
        litGrad.addColorStop(1, "rgba(255, 100, 0, 0.0)");
        ctx.fillStyle = litGrad;
        ctx.fillRect(ox, oy, w, h);
        ctx.restore();
      }}

      // Ridge highlight edge
      ctx.strokeStyle = "rgba(180, 205, 255, 0.7)";
      ctx.lineWidth = 2;
      ctx.stroke();

      // Astronomical 0° Horizon dashed line
      ctx.strokeStyle = "rgba(100, 140, 220, 0.3)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(ox, zeroY); ctx.lineTo(ox + w, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "rgba(100, 140, 220, 0.5)";
      ctx.font = "9px ui-monospace, monospace";
      ctx.textAlign = "left";
      ctx.fillText("0° Geometric Horizon", ox + 14, zeroY - 5);

      ctx.restore();
    }}

    // View: Trajectory View (Launch -> Transit -> Orbit -> Descent)
    function drawTrajectoryView(w, h, phase, t) {{
      ctx.save();
      const cx = w / 2;
      const cy = h / 2;

      // Draw a small Sun reference in the top-left of the trajectory view
      const sunX = 36;
      const sunY = 36;
      const sunR = 14;
      // Sun glow halo
      const trajSunGlow = ctx.createRadialGradient(sunX, sunY, 2, sunX, sunY, sunR * 2.4);
      trajSunGlow.addColorStop(0, "rgba(255, 184, 69, 0.55)");
      trajSunGlow.addColorStop(1, "rgba(255, 184, 69, 0)");
      ctx.fillStyle = trajSunGlow;
      ctx.beginPath();
      ctx.arc(sunX, sunY, sunR * 2.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffb845";
      ctx.beginPath();
      ctx.arc(sunX, sunY, sunR, 0, Math.PI * 2);
      ctx.fill();
      drawLabeledBody(sunX, sunY, sunR, "☀ SUN", "#ffb845",
        {{ labelDx: 0, labelDy: sunR + 22, fontSize: 11, halo: true }});

      // Draw Earth (Left) with atmospheric halo
      const earthX = w * 0.18;
      const earthY = cy;
      const earthR = 38;
      // Faint atmospheric halo (outer)
      const haloGrad = ctx.createRadialGradient(earthX, earthY, earthR, earthX, earthY, earthR * 1.35);
      haloGrad.addColorStop(0, "rgba(120, 195, 255, 0.45)");
      haloGrad.addColorStop(1, "rgba(78, 161, 255, 0)");
      ctx.fillStyle = haloGrad;
      ctx.beginPath();
      ctx.arc(earthX, earthY, earthR * 1.35, 0, Math.PI * 2);
      ctx.fill();
      const eGrad = ctx.createRadialGradient(earthX, earthY, 5, earthX, earthY, earthR);
      eGrad.addColorStop(0, "#80c4ff");
      eGrad.addColorStop(0.7, "#2875e0");
      eGrad.addColorStop(1, "#0a265c");
      ctx.fillStyle = eGrad;
      ctx.beginPath();
      ctx.arc(earthX, earthY, earthR, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("EARTH", earthX, earthY + earthR + 22);
      // Earth callout pill below the disc
      drawLabeledBody(earthX, earthY, earthR, "🌐 EARTH", "#4ea1ff",
        {{ labelDx: 0, labelDy: earthR + 36, fontSize: 11, halo: true }});

      // Draw Moon (Right) with shadow cone
      const moonX = w * 0.82;
      const moonY = cy;
      const moonR = 26;
      // Phase-driven shadow cone: a soft dark wedge covering roughly half
      // the Moon. Mirrors the real lunar terminator for the current date.
      const phaseFrac = (currentTimeSec % plan.orbit_seconds) / plan.orbit_seconds;
      const terminator = Math.cos(phaseFrac * Math.PI * 2);
      ctx.save();
      ctx.beginPath();
      ctx.arc(moonX, moonY, moonR * 1.05, 0, Math.PI * 2);
      ctx.clip();
      ctx.fillStyle = "rgba(8, 12, 24, 0.55)";
      const shadowOffset = Math.sin(phaseFrac * Math.PI * 2) * moonR * 1.05;
      ctx.fillRect(moonX - moonR * 1.2, moonY - moonR * 1.4 + shadowOffset,
                   moonR * 2.4, moonR * 2.8);
      ctx.restore();
      const mGrad = ctx.createRadialGradient(moonX, moonY, 3, moonX, moonY, moonR);
      mGrad.addColorStop(0, "#f0f4ff");
      mGrad.addColorStop(0.7, "#a2b0cb");
      mGrad.addColorStop(1, "#36425a");
      ctx.fillStyle = mGrad;
      ctx.beginPath();
      ctx.arc(moonX, moonY, moonR, 0, Math.PI * 2);
      ctx.fill();
      // Target crater at South Pole
      ctx.fillStyle = "#ff6b8a";
      ctx.beginPath();
      ctx.arc(moonX, moonY + moonR - 4, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px sans-serif";
      ctx.fillText("MOON (SOUTH POLE)", moonX, moonY + moonR + 22);
      // Moon callout pill below the disc
      drawLabeledBody(moonX, moonY, moonR, "🌙 MOON · South Pole", "#d8e1ff",
        {{ labelDx: 0, labelDy: moonR + 36, fontSize: 11, halo: true }});
      // Phase badge
      ctx.save();
      ctx.font = "9px ui-monospace, monospace";
      ctx.textAlign = "center";
      const phaseTxt = `${{(phaseFrac * 100).toFixed(0)}}% phase`;
      const bw = ctx.measureText(phaseTxt).width + 14;
      ctx.fillStyle = "rgba(11, 16, 32, 0.85)";
      ctx.strokeStyle = "rgba(120, 160, 240, 0.4)";
      ctx.lineWidth = 1;
      const bx = moonX - bw / 2;
      const by = moonY - moonR - 22;
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(bx, by, bw, 18, 6) : ctx.rect(bx, by, bw, 18);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#dde7ff";
      ctx.textBaseline = "middle";
      ctx.fillText(phaseTxt, moonX, by + 9);
      ctx.restore();

      // Trans-lunar trajectory arc
      ctx.strokeStyle = "rgba(120, 160, 240, 0.35)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(earthX, earthY);
      ctx.quadraticCurveTo(cx, cy - 80, moonX, moonY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Compute Spacecraft Position along Trajectory
      let frac = 0;
      if (phase === "LAUNCH") {{
        frac = (t / plan.launch_seconds) * 0.08;
      }} else if (phase === "TRANSIT") {{
        frac = 0.08 + ((t - plan.launch_seconds) / plan.transit_seconds) * 0.76;
      }} else if (phase === "LUNAR ORBIT") {{
        frac = 0.84 + ((t - plan.launch_seconds - plan.transit_seconds) / plan.orbit_seconds) * 0.08;
      }} else {{
        frac = 0.92 + Math.min(0.08, ((t - plan.launch_seconds - plan.transit_seconds - plan.orbit_seconds) / plan.descent_seconds) * 0.08);
      }}

      // Quadratic bezier point
      const p0 = {{ x: earthX, y: earthY }};
      const p1 = {{ x: cx, y: cy - 80 }};
      const p2 = {{ x: moonX, y: moonY }};
      const inv = 1 - frac;
      const scX = inv * inv * p0.x + 2 * inv * frac * p1.x + frac * frac * p2.x;
      const scY = inv * inv * p0.y + 2 * inv * frac * p1.y + frac * frac * p2.y;

      // Draw Spacecraft
      ctx.fillStyle = "#ff6b8a";
      ctx.beginPath();
      ctx.arc(scX, scY, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Rocket flame
      ctx.strokeStyle = "#ffb845";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(scX, scY);
      ctx.lineTo(scX - 12, scY + 3);
      ctx.stroke();

      ctx.fillStyle = "#ffb845";
      ctx.font = "bold 11px sans-serif";
      ctx.fillText("SPACECRAFT", scX, scY - 14);
      // Spacecraft pill below
      drawLabeledBody(scX, scY, 6, "🚀 SPACECRAFT", "#ff6b8a",
        {{ labelDx: 0, labelDy: 22, fontSize: 10, halo: true }});

      ctx.restore();
    }}

    // Update Side Gauges & HUD
    function updateTelemetryUI(phase, telem) {{
      phaseBadge.textContent = phase;
      phaseBadge.classList.toggle("golden", telem.sunVis && telem.earthVis);

      metVal.textContent = formatMET(currentTimeSec);
      // Append mission-total denominator beside MET for context
      const metTotalEl = document.getElementById("metTotalVal");
      if (metTotalEl) {{
        metTotalEl.textContent = "/ " + formatMET(plan.total_seconds);
      }}
      utcVal.textContent = telem.timeStr || "---";
      sunAltVal.textContent = (telem.sunAlt >= 0 ? "+" : "") + telem.sunAlt.toFixed(2) + "°";
      earthAltVal.textContent = (telem.earthAlt >= 0 ? "+" : "") + telem.earthAlt.toFixed(2) + "°";

      // Solar Gauge
      powerPctText.textContent = `${{telem.power.toFixed(0)}}%`;
      powerFill.style.width = `${{telem.power}}%`;
      if (telem.sunVis) {{
        powerStatusPill.className = "status-pill pill-active";
        powerStatusPill.textContent = "ILLUMINATED";
      }} else {{
        powerStatusPill.className = "status-pill pill-blocked";
        powerStatusPill.textContent = "SHADOWED";
      }}
      const sunClear = telem.sunAlt - telem.hSun;
      sunClearText.textContent = (sunClear >= 0 ? "+" : "") + sunClear.toFixed(2) + "°";

      // Earth Comm Gauge
      commPctText.textContent = `${{telem.comm.toFixed(0)}}%`;
      commFill.style.width = `${{telem.comm}}%`;
      if (telem.earthVis) {{
        commStatusPill.className = "status-pill pill-active";
        commStatusPill.textContent = "LINK ACTIVE";
      }} else {{
        commStatusPill.className = "status-pill pill-blocked";
        commStatusPill.textContent = "LOS BLOCKED";
      }}
      const earthClear = telem.earthAlt - telem.hEarth;
      earthClearText.textContent = (earthClear >= 0 ? "+" : "") + earthClear.toFixed(2) + "°";

      // Golden Window Banner
      if (telem.sunVis && telem.earthVis) {{
        goldenBanner.style.background = "linear-gradient(135deg, rgba(45, 212, 167, 0.25), rgba(78, 161, 255, 0.25))";
        goldenBanner.style.borderColor = "#2dd4a7";
        goldenTitle.textContent = "✦ GOLDEN WINDOW ACTIVE";
        goldenTitle.style.color = "#2dd4a7";
        goldenSub.textContent = "Simultaneous solar power generation and direct-to-Earth communication link established!";
      }} else if (telem.sunVis) {{
        goldenBanner.style.background = "rgba(12, 18, 38, 0.75)";
        goldenBanner.style.borderColor = "rgba(255, 184, 69, 0.3)";
        goldenTitle.textContent = "SOLAR POWER ONLY";
        goldenTitle.style.color = "#ffb845";
        goldenSub.textContent = "Sun is above terrain horizon. Direct communication to Earth is currently occulted.";
      }} else if (telem.earthVis) {{
        goldenBanner.style.background = "rgba(12, 18, 38, 0.75)";
        goldenBanner.style.borderColor = "rgba(78, 161, 255, 0.3)";
        goldenTitle.textContent = "COMMUNICATION ONLY";
        goldenTitle.style.color = "#4ea1ff";
        goldenSub.textContent = "Earth is in line of sight. Surface is in polar shadow (battery power required).";
      }} else {{
        goldenBanner.style.background = "rgba(12, 18, 38, 0.75)";
        goldenBanner.style.borderColor = "rgba(255, 107, 138, 0.3)";
        goldenTitle.textContent = "FULL BLACKOUT";
        goldenTitle.style.color = "#ff6b8a";
        goldenSub.textContent = "Both Sun and Earth are below the crater ridge horizon.";
      }}

      // Day Readout
      const dayCurr = (currentTimeSec / 86400).toFixed(1);
      const dayTot = (plan.total_seconds / 86400).toFixed(1);
      timeReadout.textContent = `Day ${{dayCurr}} / ${{dayTot}}`;
    }}

    // Event Listeners
    playBtn.addEventListener("click", () => {{
      isPlaying = !isPlaying;
      playBtn.textContent = isPlaying ? "⏸ Pause" : "▶ Play";
    }});

    resetBtn.addEventListener("click", () => {{
      currentTimeSec = 0;
      timeSlider.value = 0;
    }});

    // Nudge mission time by ±5% of total duration
    const nudgeFwdBtn = document.getElementById("nudgeFwdBtn");
    const nudgeBackBtn = document.getElementById("nudgeBackBtn");
    const stepFraction = 0.05;
    function nudge(dir) {{
      const delta = dir * stepFraction * plan.total_seconds;
      currentTimeSec = Math.max(0, Math.min(plan.total_seconds,
        currentTimeSec + delta));
      timeSlider.value = (currentTimeSec / plan.total_seconds) * 1000;
    }}
    nudgeFwdBtn.addEventListener("click", () => nudge(+1));
    nudgeBackBtn.addEventListener("click", () => nudge(-1));

    timeSlider.addEventListener("input", (e) => {{
      currentTimeSec = (parseFloat(e.target.value) / 1000) * plan.total_seconds;
    }});

    speedSelect.addEventListener("change", (e) => {{
      speed = parseFloat(e.target.value);
    }});

    // Phase Jump Buttons
    document.querySelectorAll(".phase-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".phase-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const frac = parseFloat(btn.dataset.time);
        currentTimeSec = frac * plan.total_seconds;
        timeSlider.value = frac * 1000;
      }});
    }});

    // View Mode Tabs
    document.querySelectorAll(".view-btn").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".view-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        activeView = btn.dataset.view;
      }});
    }});

    // Start Animation Loop
    requestAnimationFrame(render);
  </script>
</body>
</html>"""
    return html
