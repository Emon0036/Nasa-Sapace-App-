"""
Mission simulation — animated scene of launch, transit, lunar landing,
and surface observation with live Sun/Earth position.

Public API
----------
MissionPhase            enum of mission states
plan_mission(...)       build a MissionPlan for a (site, launch time, duration)
render_frame(plan, t)   return a Matplotlib figure showing the current scene
render_surface_frame    return a single-panel surface observation figure
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Wedge
from matplotlib.colors import LinearSegmentedColormap

# Don't spam the user when pre-rendering hundreds of frames
plt.rcParams["figure.max_open_warning"] = 1000

from . import ephemeris, horizon
from .sites import Site


# ---------------------------------------------------------------------------
# Mission state machine
# ---------------------------------------------------------------------------

class MissionPhase(str, Enum):
    LAUNCH              = "LAUNCH"
    TRANSIT             = "TRANSIT"
    LUNAR_ORBIT         = "LUNAR ORBIT"
    POWERED_DESCENT     = "POWERED DESCENT"
    LANDED              = "LANDED"
    SURFACE_OPS         = "SURFACE OPS"


@dataclass
class MissionPlan:
    """All the data needed to render any frame of the mission animation."""
    launch_utc: datetime
    site: Site
    profile: horizon.HorizonProfile
    # Phase boundaries, normalized to [0, 1] of total mission duration
    t_launch_end:       float = 0.005
    t_transit_end:      float = 0.45
    t_orbit_end:        float = 0.50
    t_descent_end:      float = 0.55
    # Wall-clock durations in seconds (for HUD)
    launch_seconds:     float = 600          # 10 min
    transit_seconds:    float = 3 * 86400    # 3 days
    orbit_seconds:      float = 3600         # 1 hour
    descent_seconds:    float = 3600         # 1 hour
    # Surface observation window in mission seconds (after landing)
    surface_seconds:    float = 5 * 86400    # 5 lunar days
    # Pre-computed Sun/Earth geometry for the surface-ops window
    surface_times:      List[datetime] = field(default_factory=list)
    surface_sun_alt:    np.ndarray = field(default_factory=lambda: np.array([]))
    surface_sun_az:     np.ndarray = field(default_factory=lambda: np.array([]))
    surface_earth_alt:  np.ndarray = field(default_factory=lambda: np.array([]))
    surface_earth_az:   np.ndarray = field(default_factory=lambda: np.array([]))
    horizon_at:         np.ndarray = field(default_factory=lambda: np.array([]))
    surface_earth_horizon: np.ndarray = field(default_factory=lambda: np.array([]))

    @property
    def total_seconds(self) -> float:
        return (self.launch_seconds + self.transit_seconds + self.orbit_seconds
                + self.descent_seconds + self.surface_seconds)

    def phase_at(self, t_seconds: float) -> MissionPhase:
        if t_seconds < self.launch_seconds:                     return MissionPhase.LAUNCH
        if t_seconds < self.launch_seconds + self.transit_seconds: return MissionPhase.TRANSIT
        t = t_seconds - self.launch_seconds - self.transit_seconds
        if t < self.orbit_seconds:                              return MissionPhase.LUNAR_ORBIT
        t -= self.orbit_seconds
        if t < self.descent_seconds:                            return MissionPhase.POWERED_DESCENT
        return MissionPhase.SURFACE_OPS

    def utc_at(self, t_seconds: float) -> datetime:
        return self.launch_utc + timedelta(seconds=t_seconds)


def plan_mission(site: Site,
                 launch_utc: datetime,
                 transit_days: float = 3.0,
                 surface_days: float = 5.0,
                 step_minutes: float = 10.0) -> MissionPlan:
    """Build a MissionPlan and pre-compute the surface-ops time series."""
    if transit_days < 0:
        raise ValueError("transit_days must be non-negative")
    if surface_days < 0:
        raise ValueError("surface_days must be non-negative")
    if step_minutes <= 0:
        raise ValueError("step_minutes must be positive")
    if launch_utc.tzinfo is None:
        launch_utc = launch_utc.replace(tzinfo=timezone.utc)
    profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
    landing_utc = launch_utc + timedelta(days=transit_days)
    surface_seconds = surface_days * 86400.0
    n = int(surface_seconds / (step_minutes * 60.0)) + 1
    times = [landing_utc + timedelta(minutes=step_minutes * i) for i in range(n)]
    sky = ephemeris.compute_sky(times, site.lat_deg, site.lon_deg, site.elev_m)
    horizon_sun = np.array([profile.horizon_altitude_at(az) for az in sky.sun_az])
    horizon_earth = np.array([profile.horizon_altitude_at(az) for az in sky.earth_az])
    return MissionPlan(
        launch_utc=launch_utc,
        site=site,
        profile=profile,
        launch_seconds=600,
        transit_seconds=transit_days * 86400.0,
        orbit_seconds=3600,
        descent_seconds=3600,
        surface_seconds=surface_seconds,
        surface_times=sky.times_utc.to_pydatetime().tolist(),
        surface_sun_alt=np.asarray(sky.sun_alt),
        surface_sun_az=np.asarray(sky.sun_az),
        surface_earth_alt=np.asarray(sky.earth_alt),
        surface_earth_az=np.asarray(sky.earth_az),
        horizon_at=horizon_sun,
        surface_earth_horizon=horizon_earth,
    )


def plan_to_dict(plan: MissionPlan) -> dict:
    """Serialize a MissionPlan into a JSON-compatible dict for the interactive simulator."""
    return {
        "site": {
            "id": plan.site.site_id,
            "name": plan.site.name,
            "lat": plan.site.lat_deg,
            "lon": plan.site.lon_deg,
            "elev_m": plan.site.elev_m,
            "description": plan.site.description,
        },
        "launch_utc": plan.launch_utc.isoformat(),
        "launch_seconds": float(plan.launch_seconds),
        "transit_seconds": float(plan.transit_seconds),
        "orbit_seconds": float(plan.orbit_seconds),
        "descent_seconds": float(plan.descent_seconds),
        "surface_seconds": float(plan.surface_seconds),
        "total_seconds": float(plan.total_seconds),
        "horizon_profile": {
            "azimuth_deg": [round(float(a), 1) for a in plan.profile.azimuth_deg],
            "elevation_deg": [round(float(e), 2) for e in plan.profile.elevation_deg],
        },
        "surface": {
            "times": [t.strftime("%Y-%m-%d %H:%M UTC") for t in plan.surface_times],
            "sun_alt": [round(float(a), 2) for a in plan.surface_sun_alt],
            "sun_az": [round(float(a), 2) for a in plan.surface_sun_az],
            "earth_alt": [round(float(a), 2) for a in plan.surface_earth_alt],
            "earth_az": [round(float(a), 2) for a in plan.surface_earth_az],
            "horizon_sun": [round(float(h), 2) for h in plan.horizon_at],
            "horizon_earth": [round(float(h), 2) for h in plan.surface_earth_horizon],
        }
    }


# ---------------------------------------------------------------------------
# Shared theme (must match plotting.py)
# ---------------------------------------------------------------------------

BG          = "#05070d"
PANEL       = "#0b1020"
TEXT        = "#e6ecff"
TEXT_MUTED  = "#97a3c7"
SUN         = "#ffb845"
SUN_DIM     = "#7a5520"
EARTH       = "#4ea1ff"
EARTH_DIM   = "#1f3a66"
MOON        = "#d8e1ff"
ROCKET      = "#ff6b8a"
HORIZON     = "#9aa6c8"
GRID        = "#1d2547"


def _style_axes(ax, xlim=None, ylim=None):
    ax.set_facecolor(BG)
    ax.set_xlim(xlim if xlim is not None else ax.get_xlim())
    ax.set_ylim(ylim if ylim is not None else ax.get_ylim())
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color("#3a4670")


def _draw_stars(ax, seed=7, n=70, xlim=None, ylim=None):
    """Add a stable star field so every animation frame feels like space."""
    rng = np.random.default_rng(seed)
    x0, x1 = xlim if xlim is not None else ax.get_xlim()
    y0, y1 = ylim if ylim is not None else ax.get_ylim()
    xs = rng.uniform(x0, x1, n)
    ys = rng.uniform(y0, y1, n)
    sizes = rng.uniform(2, 10, n)
    ax.scatter(xs, ys, s=sizes, color="#dce7ff", alpha=0.55,
               linewidths=0, zorder=0)


def _draw_sun(ax, x, y, radius=0.22, label=True):
    """Draw a glowing Sun marker with rays."""
    for scale, alpha in ((1.9, 0.08), (1.45, 0.16)):
        ax.add_patch(Circle((x, y), radius * scale, facecolor=SUN,
                            edgecolor="none", alpha=alpha, zorder=1))
    ax.add_patch(Circle((x, y), radius, facecolor=SUN, edgecolor="#ffe2a3",
                        linewidth=1.2, zorder=3))
    if label:
        ax.text(x, y - radius * 1.7, "SUN", color=SUN, ha="center",
                fontsize=8, weight="bold", zorder=4)


def _draw_rocket(ax, x, y, angle_deg=0, scale=1.0, thrust=True):
    """Draw a clearly visible spacecraft and optional engine plume."""
    theta = np.radians(angle_deg)
    direction = np.array([np.cos(theta), np.sin(theta)])
    normal = np.array([-direction[1], direction[0]])
    nose = np.array([x, y]) + direction * 0.16 * scale
    tail = np.array([x, y]) - direction * 0.14 * scale
    wing = 0.09 * scale
    body = np.vstack([nose, tail + normal * wing, tail - normal * wing])
    ax.fill(body[:, 0], body[:, 1], color=ROCKET, edgecolor="#ffd2df",
            linewidth=1.0, zorder=8)
    ax.scatter([x], [y], s=16 * scale, color="#f5f7ff", zorder=9)
    if thrust:
        flame_end = tail - direction * 0.22 * scale
        ax.plot([tail[0], flame_end[0]], [tail[1], flame_end[1]],
                color=SUN, linewidth=max(1.5, 4 * scale), alpha=0.9,
                solid_capstyle="round", zorder=6)
    ax.text(x, y + 0.18 * scale, "ROCKET", color=ROCKET, ha="center",
            fontsize=7, zorder=10)


# ---------------------------------------------------------------------------
# Composite multi-panel scene
# ---------------------------------------------------------------------------

def render_frame(plan: MissionPlan, t_seconds: float) -> plt.Figure:
    """Render the full mission scene at time `t_seconds`."""
    phase = plan.phase_at(t_seconds)
    fig = plt.figure(figsize=(13, 7.5), facecolor=BG)

    if phase == MissionPhase.LAUNCH:
        _render_launch(fig, plan, t_seconds)
    elif phase == MissionPhase.TRANSIT:
        _render_transit(fig, plan, t_seconds)
    elif phase == MissionPhase.LUNAR_ORBIT:
        _render_lunar_orbit(fig, plan, t_seconds)
    elif phase == MissionPhase.POWERED_DESCENT:
        _render_descent(fig, plan, t_seconds)
    else:
        _render_surface(fig, plan, t_seconds)

    _render_hud(fig, plan, t_seconds, phase)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.05,
                        wspace=0.18, hspace=0.18)
    return fig


# ---------------------------------------------------------------------------
# Phase renderers
# ---------------------------------------------------------------------------

def _render_launch(fig, plan, t):
    ax = fig.add_subplot(1, 2, 1)
    _style_axes(ax, xlim=(-1.2, 1.2), ylim=(-1.2, 1.2))
    _draw_stars(ax, seed=11, xlim=(-1.2, 1.2), ylim=(-1.2, 1.2))
    _draw_sun(ax, 0.82, 0.82, radius=0.12)
    # Earth from above
    earth = Circle((0, 0), 1.0, facecolor=EARTH, edgecolor="#9bd0ff",
                   linewidth=1.5, alpha=0.9, zorder=2)
    ax.add_patch(earth)
    # Launchpad
    pad = Rectangle((-0.06, -1.0), 0.12, 0.04, facecolor=TEXT_MUTED,
                    edgecolor="none", zorder=3)
    ax.add_patch(pad)
    # Rocket and launch trail
    frac = t / plan.launch_seconds
    h = frac * 1.6
    _draw_rocket(ax, 0, -0.92 + h, angle_deg=90, scale=0.65, thrust=frac < 1)
    ax.plot([0, 0], [-0.92, -0.92 + h], color=ROCKET, alpha=0.35,
            linestyle=":", linewidth=1.0, zorder=2)
    ax.text(0, -1.12, "EARTH LAUNCH", color=TEXT_MUTED, ha="center", fontsize=8)
    ax.set_title(f"{plan.site.name}  ·  launch from Earth",
                 color=TEXT, fontsize=11, pad=8)

    # Right panel: trajectory preview (Earth → Moon)
    ax2 = fig.add_subplot(1, 2, 2)
    _style_axes(ax2, xlim=(-1.1, 11.0), ylim=(-0.4, 0.4))
    _draw_stars(ax2, seed=12, xlim=(-1.1, 11.0), ylim=(-0.4, 0.4))
    _draw_sun(ax2, 5.0, 0.31, radius=0.08)
    ax2.add_patch(Circle((0, 0), 0.3, facecolor=EARTH, edgecolor="#9bd0ff"))
    ax2.add_patch(Circle((10, 0), 0.18, facecolor=MOON, edgecolor=TEXT))
    # Trans-lunar trajectory
    xs = np.linspace(0, 10, 200)
    ys = 0.25 * np.sin(np.pi * xs / 10)
    ax2.plot(xs, ys, color=TEXT_MUTED, linestyle="--", linewidth=1.2)
    # Rocket on trajectory
    px = min(10.0, 10.0 * (t / plan.launch_seconds) ** 0.6)
    py = 0.25 * np.sin(np.pi * px / 10)
    _draw_rocket(ax2, px, py, angle_deg=12, scale=0.45, thrust=True)
    ax2.text(0, -0.34, "EARTH", color=EARTH, ha="center", fontsize=8)
    ax2.text(10, -0.26, "MOON", color=MOON, ha="center", fontsize=8)
    ax2.set_title("Trans-lunar trajectory preview", color=TEXT, fontsize=11)


def _render_transit(fig, plan, t):
    t_in_phase = t - plan.launch_seconds
    frac = t_in_phase / plan.transit_seconds
    ax = fig.add_subplot(1, 2, 1)
    _style_axes(ax, xlim=(-1.2, 11.2), ylim=(-0.6, 0.6))
    _draw_stars(ax, seed=21, xlim=(-1.2, 11.2), ylim=(-0.6, 0.6))
    _draw_sun(ax, 5.0, 0.43, radius=0.08)
    ax.add_patch(Circle((0, 0), 0.4, facecolor=EARTH, edgecolor="#9bd0ff"))
    ax.add_patch(Circle((10, 0), 0.25, facecolor=MOON, edgecolor=TEXT))
    xs = np.linspace(0, 10, 200)
    ys = 0.35 * np.sin(np.pi * xs / 10)
    ax.plot(xs, ys, color=TEXT_MUTED, linestyle="--", linewidth=1.0, alpha=0.5)
    px = 10 * frac
    py = 0.35 * np.sin(np.pi * px / 10)
    _draw_rocket(ax, px, py, angle_deg=12, scale=0.55, thrust=False)
    ax.text(0, -0.49, "EARTH", color=EARTH, ha="center", fontsize=8)
    ax.text(10, -0.36, "MOON", color=MOON, ha="center", fontsize=8)
    ax.text(0, -0.55, f"Days elapsed: {t_in_phase/86400:.1f}",
            color=TEXT_MUTED, ha="center", fontsize=9)
    ax.set_title("Trans-lunar coast", color=TEXT, fontsize=11)

    # Right: Earth from rocket's POV (shrinking)
    ax2 = fig.add_subplot(1, 2, 2)
    _style_axes(ax2, xlim=(-1.5, 1.5), ylim=(-1.5, 1.5))
    _draw_stars(ax2, seed=22, xlim=(-1.5, 1.5), ylim=(-1.5, 1.5))
    _draw_sun(ax2, -1.05, 1.05, radius=0.12)
    r = 1.2 * (1 - 0.7 * frac)
    ax2.add_patch(Circle((0, 0), r, facecolor=EARTH, edgecolor="#9bd0ff",
                         linewidth=1.5))
    # Moon ahead
    ax2.add_patch(Circle((0.9, 0.1), 0.16 + 0.04 * frac,
                         facecolor=MOON, edgecolor=TEXT, zorder=4))
    _draw_rocket(ax2, -0.25 + 0.55 * frac, -0.35 + 0.35 * frac,
                 angle_deg=25, scale=0.5, thrust=False)
    ax2.set_title("View from the spacecraft", color=TEXT, fontsize=11)


def _render_lunar_orbit(fig, plan, t):
    t_in_phase = (t - plan.launch_seconds - plan.transit_seconds)
    frac = t_in_phase / plan.orbit_seconds
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, xlim=(-2.0, 2.0), ylim=(-2.0, 2.0))
    _draw_stars(ax, seed=31, xlim=(-2.0, 2.0), ylim=(-2.0, 2.0))
    _draw_sun(ax, -1.55, 1.45, radius=0.16)
    moon = Circle((0, 0), 0.8, facecolor=MOON, edgecolor=TEXT, linewidth=1.4)
    ax.add_patch(moon)
    # Mark landing site
    site_x = 0.8 * np.cos(np.radians(plan.site.lon_deg))
    site_y = 0.8 * np.sin(np.radians(plan.site.lon_deg))
    ax.scatter([site_x], [site_y], s=40, color=ROCKET, zorder=5)
    ax.text(site_x, site_y - 0.15, plan.site.name.split()[0],
            color=ROCKET, ha="center", fontsize=9, zorder=5)
    # Lander orbit
    theta = 2 * np.pi * frac
    orb_r = 1.5
    ox = orb_r * np.cos(theta)
    oy = orb_r * np.sin(theta)
    _draw_rocket(ax, ox, oy, angle_deg=np.degrees(theta) + 90,
                 scale=0.55, thrust=False)
    orbit_xs = orb_r * np.cos(np.linspace(0, 2*np.pi, 200))
    orbit_ys = orb_r * np.sin(np.linspace(0, 2*np.pi, 200))
    ax.plot(orbit_xs, orbit_ys, color=TEXT_MUTED, linestyle="--",
            linewidth=1.0, alpha=0.5)
    ax.set_title("Lunar orbit insertion", color=TEXT, fontsize=11)


def _render_descent(fig, plan, t):
    t_in_phase = (t - plan.launch_seconds - plan.transit_seconds
                  - plan.orbit_seconds)
    frac = t_in_phase / plan.descent_seconds
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, xlim=(-1.2, 1.2), ylim=(-1.2, 1.2))
    _draw_stars(ax, seed=41, xlim=(-1.2, 1.2), ylim=(-1.2, 1.2))
    _draw_sun(ax, -0.85, 0.82, radius=0.13)
    moon = Circle((0, 0), 0.95, facecolor=MOON, edgecolor=TEXT, linewidth=1.4)
    ax.add_patch(moon)
    # Lander altitude (decreasing)
    alt = 1.15 - 0.30 * frac
    lander_x = 0.8 * np.cos(np.radians(plan.site.lon_deg))
    lander_y = 0.8 * np.sin(np.radians(plan.site.lon_deg))
    # Connect with thrust trail
    ax.plot([lander_x, lander_x], [lander_y + 0.3, lander_y], color=ROCKET,
            linestyle=":", linewidth=1.4, alpha=0.8)
    _draw_rocket(ax, lander_x, lander_y + 0.3 * (1 - frac),
                 angle_deg=-90, scale=0.65, thrust=frac < 0.98)
    # Target marker
    ax.scatter([lander_x], [lander_y], s=80, marker="x",
               color=SUN, linewidths=2.0, zorder=5)
    ax.set_title(f"Powered descent — altitude {(1-frac)*100:.0f}% to go",
                 color=TEXT, fontsize=11)


def _render_surface(fig, plan, t):
    """Surface observation panel: polar view + altitude timeline."""
    t_in_phase = (t - plan.launch_seconds - plan.transit_seconds
                  - plan.orbit_seconds - plan.descent_seconds)
    idx = int(np.clip(t_in_phase / plan.surface_seconds *
                      (len(plan.surface_times) - 1), 0,
                      len(plan.surface_times) - 1))
    sun_alt = float(plan.surface_sun_alt[idx])
    sun_az  = float(plan.surface_sun_az[idx])
    earth_alt = float(plan.surface_earth_alt[idx])
    earth_az  = float(plan.surface_earth_az[idx])
    horizon_alt = float(plan.horizon_at[idx])

    # ----- Left: 3D-feeling surface scene -----
    ax = fig.add_subplot(1, 2, 1, projection="polar")
    ax.set_facecolor(BG)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    az = np.asarray(plan.profile.azimuth_deg)
    alt = np.asarray(plan.profile.elevation_deg)
    r = 90 - alt
    ax.plot(np.radians(az), r, "--", color=HORIZON, linewidth=1.4,
            label="Horizon mask")
    ax.fill(np.radians(az), r, color=HORIZON, alpha=0.10)
    # Sun + Earth markers
    _draw_body(ax, sun_az, sun_alt, SUN, "Sun", size=120)
    _draw_body(ax, earth_az, earth_alt, EARTH, "Earth", size=140)
    # Lander dot at site
    ax.scatter([0], [0], s=40, marker="^", color=ROCKET, zorder=10)
    ax.text(np.radians(plan.site.lon_deg), 4, plan.site.name,
            color=ROCKET, ha="center", fontsize=8)
    ax.set_ylim(0, 90)
    ax.set_yticks([0, 30, 60, 90])
    ax.set_yticklabels(["90°", "60°", "30°", "0°"], color=TEXT_MUTED, fontsize=8)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"], color=TEXT, fontsize=9)
    ax.grid(color=GRID, alpha=0.6)
    ax.spines["polar"].set_color("#3a4670")
    ax.set_title("Live sky from the lander", color=TEXT, fontsize=11, pad=12)

    # ----- Right: power + comm gauges + altitude history -----
    ax2 = fig.add_subplot(1, 2, 2)
    ax2.set_facecolor(PANEL)
    sun_visible  = sun_alt > horizon_alt
    earth_visible = earth_alt > horizon_alt
    power_pct   = max(0.0, (sun_alt / 90.0)) * 100 if sun_visible else 0.0
    # comm_pct uses how far Earth is above horizon
    comm_pct    = max(0.0, min(1.0, (earth_alt - horizon_alt) / 30.0)) * 100 \
                  if earth_visible else 0.0

    # Power gauge
    _gauge(ax2, 0.15, 0.78, power_pct, SUN, "Solar power")
    # Comm gauge
    _gauge(ax2, 0.55, 0.78, comm_pct, EARTH, "Direct-to-Earth")
    # Numeric readouts
    ax2.text(0.05, 0.40,
             f"Sun altitude: {sun_alt:+.2f}°\n"
             f"Sun azimuth: {sun_az:.1f}°\n"
             f"Horizon at Sun: {horizon_alt:.2f}°\n"
             f"Earth altitude: {earth_alt:+.2f}°\n"
             f"Earth azimuth: {earth_az:.1f}°",
             color=TEXT, fontsize=10, family="monospace",
             verticalalignment="top")
    # Mini history strip
    n = len(plan.surface_sun_alt)
    start = max(0, idx - 80)
    end   = min(n, idx + 80)
    ax3 = fig.add_axes([0.55, 0.05, 0.40, 0.18])
    ax3.set_facecolor(PANEL)
    tslice = np.arange(start, end)
    ax3.fill_between(tslice, 0, plan.surface_sun_alt[start:end],
                     color=SUN, alpha=0.25)
    ax3.plot(tslice, plan.surface_sun_alt[start:end], color=SUN, linewidth=1.4)
    ax3.plot(tslice, plan.surface_earth_alt[start:end], color=EARTH, linewidth=1.2)
    ax3.axvline(idx, color=ROCKET, linewidth=1.0)
    ax3.set_ylim(-20, 90)
    ax3.tick_params(colors=TEXT_MUTED, labelsize=7)
    for s in ax3.spines.values():
        s.set_color("#3a4670")
    ax3.set_title("Recent altitude history", color=TEXT, fontsize=9, pad=4)


# ---------------------------------------------------------------------------
# HUD overlay
# ---------------------------------------------------------------------------

def _render_hud(fig, plan, t, phase: MissionPhase):
    elapsed_h = t / 3600.0
    utc = plan.utc_at(t)
    sun_visible = "—"
    earth_visible = "—"
    if phase == MissionPhase.SURFACE_OPS:
        t_in = (t - plan.launch_seconds - plan.transit_seconds
                - plan.orbit_seconds - plan.descent_seconds)
        idx = int(np.clip(t_in / plan.surface_seconds *
                          (len(plan.surface_times) - 1), 0,
                          len(plan.surface_times) - 1))
        sa = float(plan.surface_sun_alt[idx])
        ha = float(plan.horizon_at[idx])
        ea = float(plan.surface_earth_alt[idx])
        sun_visible   = "ON" if sa > ha else "OFF"
        earth_visible = "ON" if ea > ha else "OFF"

    text = (f"PHASE: {phase.value}     "
            f"T+{elapsed_h:7.2f} h     "
            f"UTC {utc:%Y-%m-%d %H:%M}     "
            f"SUN: {sun_visible}     "
            f"EARTH: {earth_visible}     "
            f"SITE: {plan.site.name}")
    fig.text(0.5, 0.965, text, color=TEXT, ha="center", va="top",
             fontsize=11, family="monospace",
             bbox=dict(facecolor=PANEL, edgecolor="#3a4670", boxstyle="round,pad=0.4"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _draw_body(ax, az_deg, alt_deg, color, label, size):
    if alt_deg < 0:
        # Below horizon — render faintly below the rim
        r = 90 - max(alt_deg, -90)
        ax.scatter([np.radians(az_deg)], [r], s=size * 0.4, color=color,
                   alpha=0.25, zorder=3, label=f"{label} (below)")
        return
    r = 90 - alt_deg
    ax.scatter([np.radians(az_deg)], [r], s=size, color=color,
               edgecolor="white", linewidth=0.8, zorder=5, label=label)


def _gauge(ax, x, y, pct, color, title):
    # ax is the figure coords frame; convert
    width, height = 0.30, 0.30
    # Background arc
    bg = Wedge((x + width/2, y - height/2), height/2 - 0.01, 0, 180,
               width=width - height/2, facecolor=PANEL, edgecolor="#3a4670",
               linewidth=1)
    ax.add_patch(bg)
    # Filled arc (semi-circle)
    end_angle = 180 * (1 - pct / 100.0)
    fg = Wedge((x + width/2, y - height/2), height/2 - 0.01, end_angle, 180,
               width=width - height/2, facecolor=color, edgecolor="none",
               alpha=0.85)
    ax.add_patch(fg)
    ax.text(x + width/2, y - 0.02, f"{pct:.0f}%", ha="center", va="center",
            color=TEXT, fontsize=14, weight="bold")
    ax.text(x + width/2, y + 0.04, title, ha="center", va="center",
            color=TEXT_MUTED, fontsize=9)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


# ---------------------------------------------------------------------------
# Convenience for streamlit: build a sequence of frames
# ---------------------------------------------------------------------------

def build_frame_sequence(plan: MissionPlan,
                         n_frames: int = 240,
                         fps: float = 30.0,
                         surface_focus: bool = True) -> List[Tuple[float, plt.Figure]]:
    """Pre-render `n_frames` evenly spaced frames.

    If `surface_focus` is True, the majority of frames cover surface ops.
    """
    seq: List[Tuple[float, plt.Figure]] = []
    if surface_focus:
        # 5% pre-surface, 95% surface
        n_pre = max(1, n_frames // 20)
        n_surf = n_frames - n_pre
        # Pre-surface frames
        for i in range(n_pre):
            t = (plan.total_seconds - plan.surface_seconds) * (i / max(1, n_pre - 1))
            seq.append((t, render_frame(plan, t)))
        for i in range(n_surf):
            frac = i / max(1, n_surf - 1)
            t = (plan.total_seconds - plan.surface_seconds) + frac * plan.surface_seconds
            fig = render_frame(plan, t)
            seq.append((t, fig))
            plt.close(fig)
    else:
        for i in range(n_frames):
            t = plan.total_seconds * (i / max(1, n_frames - 1))
            fig = render_frame(plan, t)
            seq.append((t, fig))
            plt.close(fig)
    return seq
