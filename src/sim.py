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
try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, Rectangle, Wedge
    from matplotlib.colors import LinearSegmentedColormap
    MATPLOTLIB_AVAILABLE = True
except Exception:
    plt = None  # type: ignore[assignment]
    Circle = FancyArrowPatch = Rectangle = Wedge = LinearSegmentedColormap = None  # type: ignore[assignment]
    MATPLOTLIB_AVAILABLE = False

# Don't spam the user when pre-rendering hundreds of frames
if MATPLOTLIB_AVAILABLE:
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
    if launch_utc.tzinfo is None:
        launch_utc = launch_utc.replace(tzinfo=timezone.utc)
    configured_profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
    if configured_profile.source == "dem":
        profile = configured_profile
    else:
        # Use the geometric horizon as the scientific visibility boundary.
        # Synthetic ridge curves may be shown as illustrations elsewhere, but
        # are not treated as measured terrain in computed telemetry.
        profile = horizon.HorizonProfile(
            azimuth_deg=np.linspace(0.0, 360.0, 360, endpoint=False),
            elevation_deg=np.zeros(360, dtype=float),
            site_lat_deg=site.lat_deg,
            site_lon_deg=site.lon_deg,
            site_elev_m=site.elev_m,
            source="geometric",
        )
    launch_seconds = 600.0
    transit_seconds = transit_days * 86400.0
    orbit_seconds = 3600.0
    descent_seconds = 3600.0
    surface_start_seconds = launch_seconds + transit_seconds + orbit_seconds + descent_seconds
    landing_utc = launch_utc + timedelta(seconds=surface_start_seconds)
    surface_seconds = surface_days * 86400.0
    n = int(surface_seconds / (step_minutes * 60.0)) + 1
    times = [landing_utc + timedelta(minutes=step_minutes * i) for i in range(n)]
    sky = ephemeris.compute_sky(
        times, site.lat_deg, site.lon_deg, site.elev_m, site_id=site.site_id)
    horizon_at = np.array([profile.horizon_altitude_at(az) for az in sky.sun_az])
    return MissionPlan(
        launch_utc=launch_utc,
        site=site,
        profile=profile,
        launch_seconds=launch_seconds,
        transit_seconds=transit_seconds,
        orbit_seconds=orbit_seconds,
        descent_seconds=descent_seconds,
        surface_seconds=surface_seconds,
        surface_times=sky.times_utc.to_pydatetime().tolist(),
        surface_sun_alt=np.asarray(sky.sun_alt),
        surface_sun_az=np.asarray(sky.sun_az),
        surface_earth_alt=np.asarray(sky.earth_alt),
        surface_earth_az=np.asarray(sky.earth_az),
        horizon_at=horizon_at,
    )


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


# ---------------------------------------------------------------------------
# Composite multi-panel scene
# ---------------------------------------------------------------------------

def render_frame(plan: MissionPlan, t_seconds: float) -> plt.Figure:
    """Render the full mission scene at time `t_seconds`."""
    if not MATPLOTLIB_AVAILABLE:
        raise RuntimeError("The Matplotlib native plotting backend is unavailable")
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
    # Earth from above
    earth = Circle((0, 0), 1.0, facecolor=EARTH, edgecolor="#9bd0ff",
                   linewidth=1.5, alpha=0.9, zorder=2)
    ax.add_patch(earth)
    # Launchpad
    pad = Rectangle((-0.06, -1.0), 0.12, 0.04, facecolor=TEXT_MUTED,
                    edgecolor="none", zorder=3)
    ax.add_patch(pad)
    # Rocket trail
    frac = t / plan.launch_seconds
    h = frac * 1.6
    rocket = Rectangle((-0.02, -1.0 + h), 0.04, 0.08, facecolor=ROCKET,
                       edgecolor="#ffb8d2", zorder=4)
    ax.add_patch(rocket)
    flame = Wedge((0, -1.0 + h), 0.05, 250, 290, facecolor=SUN,
                  edgecolor="none", alpha=0.85, zorder=3)
    ax.add_patch(flame)
    ax.set_title(f"{plan.site.name}  ·  launch from Earth",
                 color=TEXT, fontsize=11, pad=8)

    # Right panel: trajectory preview (Earth → Moon)
    ax2 = fig.add_subplot(1, 2, 2)
    _style_axes(ax2, xlim=(-1.1, 11.0), ylim=(-0.4, 0.4))
    ax2.add_patch(Circle((0, 0), 0.3, facecolor=EARTH, edgecolor="#9bd0ff"))
    ax2.add_patch(Circle((10, 0), 0.18, facecolor=MOON, edgecolor=TEXT))
    # Trans-lunar trajectory
    xs = np.linspace(0, 10, 200)
    ys = 0.25 * np.sin(np.pi * xs / 10)
    ax2.plot(xs, ys, color=TEXT_MUTED, linestyle="--", linewidth=1.2)
    # Rocket on trajectory
    px = min(10.0, 10.0 * (t / plan.launch_seconds) ** 0.6)
    py = 0.25 * np.sin(np.pi * px / 10)
    ax2.scatter([px], [py], s=70, color=ROCKET, edgecolor="#ffb8d2",
                zorder=4)
    ax2.set_title("Trans-lunar trajectory preview", color=TEXT, fontsize=11)


def _render_transit(fig, plan, t):
    t_in_phase = t - plan.launch_seconds
    frac = t_in_phase / plan.transit_seconds
    ax = fig.add_subplot(1, 2, 1)
    _style_axes(ax, xlim=(-1.2, 11.2), ylim=(-0.6, 0.6))
    ax.add_patch(Circle((0, 0), 0.4, facecolor=EARTH, edgecolor="#9bd0ff"))
    ax.add_patch(Circle((10, 0), 0.25, facecolor=MOON, edgecolor=TEXT))
    xs = np.linspace(0, 10, 200)
    ys = 0.35 * np.sin(np.pi * xs / 10)
    ax.plot(xs, ys, color=TEXT_MUTED, linestyle="--", linewidth=1.0, alpha=0.5)
    px = 10 * frac
    py = 0.35 * np.sin(np.pi * px / 10)
    ax.scatter([px], [py], s=80, color=ROCKET, edgecolor="#ffb8d2", zorder=4)
    ax.text(0, -0.55, f"Days elapsed: {t_in_phase/86400:.1f}",
            color=TEXT_MUTED, ha="center", fontsize=9)
    ax.set_title("Trans-lunar coast", color=TEXT, fontsize=11)

    # Right: Earth from rocket's POV (shrinking)
    ax2 = fig.add_subplot(1, 2, 2)
    _style_axes(ax2, xlim=(-1.5, 1.5), ylim=(-1.5, 1.5))
    r = 1.2 * (1 - 0.7 * frac)
    ax2.add_patch(Circle((0, 0), r, facecolor=EARTH, edgecolor="#9bd0ff",
                         linewidth=1.5))
    # Moon ahead
    ax2.scatter([0.9], [0.1], s=300 * (0.3 + frac), color=MOON,
                edgecolor=TEXT, zorder=4)
    ax2.set_title("View from the spacecraft", color=TEXT, fontsize=11)


def _render_lunar_orbit(fig, plan, t):
    t_in_phase = (t - plan.launch_seconds - plan.transit_seconds)
    frac = t_in_phase / plan.orbit_seconds
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, xlim=(-2.0, 2.0), ylim=(-2.0, 2.0))
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
    ax.add_patch(Circle((ox, oy), 0.05, facecolor=ROCKET,
                        edgecolor="#ffb8d2", zorder=4))
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
    moon = Circle((0, 0), 0.95, facecolor=MOON, edgecolor=TEXT, linewidth=1.4)
    ax.add_patch(moon)
    # Lander altitude (decreasing)
    alt = 1.15 - 0.30 * frac
    lander_x = 0.8 * np.cos(np.radians(plan.site.lon_deg))
    lander_y = 0.8 * np.sin(np.radians(plan.site.lon_deg))
    # Connect with thrust trail
    ax.plot([lander_x, lander_x], [lander_y + 0.3, lander_y], color=ROCKET,
            linestyle=":", linewidth=1.4, alpha=0.8)
    ax.scatter([lander_x], [lander_y + 0.3 * (1 - frac)],
               s=80, color=ROCKET, edgecolor="#ffb8d2", zorder=4)
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
    if not MATPLOTLIB_AVAILABLE:
        return [(0.0, None)]  # type: ignore[list-item]
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
