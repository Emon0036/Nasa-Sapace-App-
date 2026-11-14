"""
Plotting helpers — dark "space" theme.

All Plotly figures use transparent backgrounds, neon colors, and a
consistent grid style so they blend with the rest of the UI.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    _PLOTLY_OK = True
except Exception:
    _PLOTLY_OK = False
    go = None  # type: ignore
    make_subplots = None  # type: ignore

try:
    import matplotlib.pyplot as plt
    _MATPLOTLIB_OK = True
except Exception:
    plt = None  # type: ignore[assignment]
    _MATPLOTLIB_OK = False

from . import horizon


# ---------------------------------------------------------------------------
# Shared theme constants
# ---------------------------------------------------------------------------

COLOR_BG          = "rgba(0,0,0,0)"
COLOR_GRID        = "rgba(120,150,220,0.12)"
COLOR_AXIS        = "rgba(180,200,255,0.55)"
COLOR_TEXT        = "#e6ecff"
COLOR_TEXT_MUTED  = "#97a3c7"
COLOR_SUN         = "#ffb845"
COLOR_SUN_GLOW    = "rgba(255,184,69,0.45)"
COLOR_EARTH       = "#4ea1ff"
COLOR_EARTH_GLOW  = "rgba(78,161,255,0.45)"
COLOR_HORIZON     = "rgba(200,210,255,0.55)"
COLOR_HORIZON_FILL= "rgba(120,150,220,0.10)"

MPL_BG          = "#05070d"
MPL_PANEL       = "#0b1020"
MPL_TEXT        = "#e6ecff"
MPL_TEXT_MUTED  = "#97a3c7"
MPL_SUN         = "#ffb845"
MPL_EARTH       = "#4ea1ff"
MPL_HORIZON     = "#9aa6c8"


def _apply_dark_layout(fig, height: int = 500) -> None:
    fig.update_layout(
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        font=dict(family="Space Grotesk, sans-serif", color=COLOR_TEXT, size=12),
        height=height,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            bgcolor="rgba(18,24,44,0.45)",
            bordercolor="rgba(120,150,220,0.25)",
            borderwidth=1,
            font=dict(color=COLOR_TEXT, size=11),
        ),
        title=dict(
            font=dict(color=COLOR_TEXT, size=15, family="Space Grotesk, sans-serif"),
            x=0.02, xanchor="left",
        ),
    )


def sky_polar_plotly(df: pd.DataFrame,
                     title: str = "Sky track",
                     horizon_profile: Optional[horizon.HorizonProfile] = None,
                     height: int = 520) -> "go.Figure":
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")

    fig = go.Figure()

    if horizon_profile is not None:
        az = np.asarray(horizon_profile.azimuth_deg)
        alt = np.asarray(horizon_profile.elevation_deg)
        fig.add_trace(go.Scatterpolar(
            r=90 - alt,
            theta=az,
            mode="lines",
            name="Horizon mask",
            line=dict(color=COLOR_HORIZON, width=2, dash="dash"),
            fill="toself",
            fillcolor=COLOR_HORIZON_FILL,
            hovertemplate="azimuth %{theta:.1f}°<br>horizon alt %{customdata:.1f}°<extra></extra>",
            customdata=alt,
        ))

    fig.add_trace(go.Scatterpolar(
        r=90 - df["earth_alt_deg"].clip(lower=0),
        theta=df["earth_az_deg"],
        mode="markers",
        name="Earth",
        marker=dict(color=COLOR_EARTH, size=7,
                    line=dict(color=COLOR_EARTH_GLOW, width=1)),
        hovertemplate="Earth<br>az %{theta:.1f}°<br>alt %{customdata:.1f}°<extra></extra>",
        customdata=df["earth_alt_deg"],
    ))

    fig.add_trace(go.Scatterpolar(
        r=90 - df["sun_alt_deg"].clip(lower=0),
        theta=df["sun_az_deg"],
        mode="markers",
        name="Sun",
        marker=dict(color=COLOR_SUN, size=5,
                    line=dict(color=COLOR_SUN_GLOW, width=1)),
        hovertemplate="Sun<br>az %{theta:.1f}°<br>alt %{customdata:.1f}°<extra></extra>",
        customdata=df["sun_alt_deg"],
    ))

    fig.update_layout(
        polar=dict(
            bgcolor=COLOR_BG,
            radialaxis=dict(
                range=[0, 90],
                tickvals=[0, 30, 60, 90],
                ticktext=["90°", "60°", "30°", "0°"],
                angle=90, tickangle=90,
                gridcolor=COLOR_GRID,
                linecolor=COLOR_AXIS,
                tickfont=dict(color=COLOR_TEXT_MUTED, size=10),
            ),
            angularaxis=dict(
                direction="clockwise",
                rotation=90,
                tickvals=[0, 90, 180, 270],
                ticktext=["N", "E", "S", "W"],
                gridcolor=COLOR_GRID,
                linecolor=COLOR_AXIS,
                tickfont=dict(color=COLOR_TEXT, size=11),
            ),
        ),
        title=title,
    )
    _apply_dark_layout(fig, height=height)
    return fig


def elevation_vs_time_plotly(df: pd.DataFrame,
                             horizon_profile: Optional[horizon.HorizonProfile] = None,
                             title: str = "Altitude vs time",
                             height: int = 600) -> "go.Figure":
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        subplot_titles=("Sun altitude", "Earth altitude"),
        vertical_spacing=0.10,
    )

    if horizon_profile is not None:
        h_sun = np.array([horizon_profile.horizon_altitude_at(az) for az in df["sun_az_deg"]])
        h_earth = np.array([horizon_profile.horizon_altitude_at(az) for az in df["earth_az_deg"]])
        fig.add_trace(go.Scatter(
            x=df["time_utc"], y=h_sun, mode="lines",
            name="Sun horizon (terrain)",
            line=dict(color=COLOR_HORIZON, width=1.4, dash="dash"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df["time_utc"], y=h_earth, mode="lines",
            name="Earth horizon (terrain)",
            line=dict(color=COLOR_HORIZON, width=1.4, dash="dash"),
            showlegend=False,
        ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df["time_utc"], y=df["sun_alt_deg"],
        mode="lines", name="Sun",
        line=dict(color=COLOR_SUN, width=2.4),
        fill="tozeroy",
        fillcolor="rgba(255,184,69,0.12)",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df["time_utc"], y=df["earth_alt_deg"],
        mode="lines", name="Earth",
        line=dict(color=COLOR_EARTH, width=2.4),
        fill="tozeroy",
        fillcolor="rgba(78,161,255,0.10)",
    ), row=2, col=1)

    for r in (1, 2):
        fig.add_hline(y=0, line_color=COLOR_AXIS, line_width=1, row=r, col=1)

    fig.update_yaxes(title_text="altitude (°)", gridcolor=COLOR_GRID,
                     zerolinecolor=COLOR_AXIS,
                     tickfont=dict(color=COLOR_TEXT_MUTED),
                     title_font=dict(color=COLOR_TEXT_MUTED),
                     row=1, col=1)
    fig.update_yaxes(title_text="altitude (°)", gridcolor=COLOR_GRID,
                     zerolinecolor=COLOR_AXIS,
                     tickfont=dict(color=COLOR_TEXT_MUTED),
                     title_font=dict(color=COLOR_TEXT_MUTED),
                     row=2, col=1)
    fig.update_xaxes(gridcolor=COLOR_GRID,
                     tickfont=dict(color=COLOR_TEXT_MUTED),
                     title_font=dict(color=COLOR_TEXT_MUTED),
                     row=2, col=1, title_text="UTC time")

    fig.update_layout(
        title=title,
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(18,24,44,0.95)",
                        bordercolor=COLOR_EARTH,
                        font=dict(color=COLOR_TEXT)),
    )
    _apply_dark_layout(fig, height=height)
    return fig


def date_sweep_heatmap_plotly(sweeps: dict, metric: str, title: str) -> "go.Figure":
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")

    site_names = list(sweeps.keys())
    dates = sweeps[site_names[0]]["date_utc"].tolist()
    z = np.array([sweeps[s][metric].values for s in site_names])

    colorscale = [
        [0.0,  "rgba(11,16,32,0.6)"],
        [0.3,  "rgba(78,161,255,0.5)"],
        [0.7,  "rgba(255,184,69,0.7)"],
        [1.0,  "rgba(255,107,138,0.9)"],
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=dates, y=site_names,
        colorscale=colorscale,
        colorbar=dict(
            title=dict(text=metric, font=dict(color=COLOR_TEXT_MUTED)),
            tickfont=dict(color=COLOR_TEXT_MUTED),
            outlinecolor=COLOR_AXIS, outlinewidth=1,
        ),
        hovertemplate="%{y}<br>%{x}<br>" + metric + " = %{z:.1f}<extra></extra>",
        xgap=2, ygap=2,
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title=dict(text="Date", font=dict(color=COLOR_TEXT_MUTED)),
                   tickfont=dict(color=COLOR_TEXT_MUTED),
                   gridcolor=COLOR_GRID),
        yaxis=dict(title=dict(text="Site", font=dict(color=COLOR_TEXT_MUTED)),
                   tickfont=dict(color=COLOR_TEXT),
                   gridcolor=COLOR_GRID),
    )
    _apply_dark_layout(fig, height=max(320, 80 + 44 * len(site_names)))
    return fig


# ---------------------------------------------------------------------------
# Matplotlib (static fallback / small multiples)
# ---------------------------------------------------------------------------

def _mpl_dark_style():
    if not _MATPLOTLIB_OK:
        raise RuntimeError("Matplotlib's native plotting backend is unavailable")
    plt.rcParams.update({
        "figure.facecolor":  MPL_BG,
        "axes.facecolor":    MPL_BG,
        "axes.edgecolor":    "#3a4670",
        "axes.labelcolor":   MPL_TEXT_MUTED,
        "xtick.color":       MPL_TEXT_MUTED,
        "ytick.color":       MPL_TEXT_MUTED,
        "grid.color":        "#1d2547",
        "grid.alpha":        0.55,
        "text.color":        MPL_TEXT,
        "font.family":       "DejaVu Sans",
    })


def sky_polar_mpl(df: pd.DataFrame,
                  horizon_profile: Optional[horizon.HorizonProfile] = None,
                  title: str = "Sky track",
                  ax: Optional["plt.Axes"] = None) -> "plt.Axes":
    _mpl_dark_style()
    if ax is None:
        _, ax = plt.subplots(subplot_kw=dict(projection="polar"), figsize=(6, 6))
    ax.set_facecolor(MPL_BG)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)

    if horizon_profile is not None:
        az = np.radians(np.asarray(horizon_profile.azimuth_deg))
        r = 90 - np.asarray(horizon_profile.elevation_deg)
        ax.plot(np.concatenate([az, az[:1]]), np.concatenate([r, r[:1]]),
                "--", color=MPL_HORIZON, linewidth=1.4, label="Horizon")
        ax.fill(np.concatenate([az, az[:1]]), np.concatenate([r, r[:1]]),
                color=MPL_HORIZON, alpha=0.12)

    r_sun = 90 - df["sun_alt_deg"].clip(lower=0)
    r_earth = 90 - df["earth_alt_deg"].clip(lower=0)
    ax.scatter(np.radians(df["sun_az_deg"]), r_sun, s=10,
               color=MPL_SUN, edgecolor="#ffd07a", linewidth=0.4,
               label="Sun", zorder=3)
    ax.scatter(np.radians(df["earth_az_deg"]), r_earth, s=14,
               color=MPL_EARTH, edgecolor="#9bd0ff", linewidth=0.4,
               label="Earth", zorder=3)

    ax.set_ylim(0, 90)
    ax.set_yticks([0, 30, 60, 90])
    ax.set_yticklabels(["90°", "60°", "30°", "0°"], color=MPL_TEXT_MUTED)
    ax.set_xticks(np.radians([0, 90, 180, 270]))
    ax.set_xticklabels(["N", "E", "S", "W"], color=MPL_TEXT)
    ax.grid(color="#1d2547", alpha=0.55)
    ax.spines["polar"].set_color("#3a4670")
    ax.set_title(title, color=MPL_TEXT, pad=14, fontsize=11)
    ax.legend(loc="lower right", fontsize=8, facecolor=MPL_PANEL,
              edgecolor="#3a4670", labelcolor=MPL_TEXT)
    return ax


def comparison_grid_mpl(dfs: dict, title: str = "Site comparison"):
    if not _MATPLOTLIB_OK:
        raise RuntimeError("Matplotlib's native plotting backend is unavailable")
    n = len(dfs)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, subplot_kw=dict(projection="polar"),
                             figsize=(4.2 * cols, 4.2 * rows))
    fig.patch.set_facecolor(MPL_BG)
    axes = np.atleast_2d(axes).reshape(rows, cols)
    for ax, (name, (df, prof)) in zip(axes.flat, dfs.items()):
        sky_polar_mpl(df, prof, title=name, ax=ax)
    for ax in axes.flat[len(dfs):]:
        ax.set_visible(False)
    fig.suptitle(title, color=MPL_TEXT, fontsize=14, y=1.02)
    fig.tight_layout()
    return fig


def comparison_grid_plotly(dfs: dict, title: str = "Site comparison") -> "go.Figure":
    """Interactive cross-site altitude tracks; works without Matplotlib."""
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")
    names = list(dfs)
    if not names:
        raise ValueError("At least one site is required for comparison")
    fig = make_subplots(
        rows=len(names), cols=1, shared_xaxes=True,
        subplot_titles=names, vertical_spacing=min(0.08, 0.3 / len(names)),
    )
    for row, name in enumerate(names, start=1):
        frame, _profile = dfs[name]
        fig.add_trace(go.Scatter(
            x=frame["time_utc"], y=frame["sun_alt_deg"],
            mode="lines", name="Sun", legendgroup="sun",
            showlegend=(row == 1), line=dict(color=COLOR_SUN),
        ), row=row, col=1)
        fig.add_trace(go.Scatter(
            x=frame["time_utc"], y=frame["earth_alt_deg"],
            mode="lines", name="Earth", legendgroup="earth",
            showlegend=(row == 1), line=dict(color=COLOR_EARTH),
        ), row=row, col=1)
        fig.add_hline(y=0.0, line_dash="dot", line_color=COLOR_HORIZON, row=row, col=1)
        fig.update_yaxes(title_text="Altitude (°)", row=row, col=1)
    fig.update_xaxes(title_text="UTC", row=len(names), col=1)
    _apply_dark_layout(fig, height=max(360, 240 * len(names)))
    fig.update_layout(title=title)
    return fig


def mission_surface_timeline(times, sun_alt, earth_alt, horizon_alt, *, title: str) -> "go.Figure":
    """Plot the surface-operations window when the Matplotlib animation is unavailable."""
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=times, y=sun_alt, mode="lines", name="Sun altitude",
        line=dict(color=COLOR_SUN, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=times, y=earth_alt, mode="lines", name="Earth altitude",
        line=dict(color=COLOR_EARTH, width=2),
    ))
    fig.add_trace(go.Scatter(
        x=times, y=horizon_alt, mode="lines", name="Selected horizon profile",
        line=dict(color=COLOR_HORIZON, width=1.5, dash="dash"),
    ))
    fig.add_hline(y=0, line_color=COLOR_AXIS, line_dash="dot")
    fig.update_yaxes(title_text="Altitude (°)", range=[-15, 15], zeroline=False)
    fig.update_xaxes(title_text="UTC")
    _apply_dark_layout(fig, height=420)
    fig.update_layout(title=title)
    return fig
