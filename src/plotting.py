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

import matplotlib.pyplot as plt

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
                     height: int = 520,
                     current_index: Optional[int] = None) -> "go.Figure":
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

    if current_index is not None and len(df):
        i = int(np.clip(current_index, 0, len(df) - 1))
        fig.add_trace(go.Scatterpolar(
            r=[max(0.0, 90.0 - float(df.iloc[i]["sun_alt_deg"]))],
            theta=[float(df.iloc[i]["sun_az_deg"])],
            mode="markers+text", name="Current Sun",
            text=["SUN NOW"], textposition="top center",
            marker=dict(color=COLOR_SUN, size=14, symbol="star",
                        line=dict(color="white", width=1)),
            hovertemplate=("Sun now<br>UTC %{customdata[0]}<br>"
                           "az %{theta:.2f}Â°<br>alt %{customdata[1]:+.2f}Â°<extra></extra>"),
            customdata=[[str(df.iloc[i]["time_utc"]), float(df.iloc[i]["sun_alt_deg"])]],
        ))
        fig.add_trace(go.Scatterpolar(
            r=[max(0.0, 90.0 - float(df.iloc[i]["earth_alt_deg"]))],
            theta=[float(df.iloc[i]["earth_az_deg"])],
            mode="markers+text", name="Current Earth",
            text=["EARTH NOW"], textposition="top center",
            marker=dict(color=COLOR_EARTH, size=14, symbol="diamond",
                        line=dict(color="white", width=1)),
            hovertemplate=("Earth now<br>UTC %{customdata[0]}<br>"
                           "az %{theta:.2f}Â°<br>alt %{customdata[1]:+.2f}Â°<extra></extra>"),
            customdata=[[str(df.iloc[i]["time_utc"]), float(df.iloc[i]["earth_alt_deg"])]],
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


def astronaut_ground_view_plotly(
    df: pd.DataFrame,
    horizon_profile: horizon.HorizonProfile,
    current_index: int,
    title: str = "Astronaut ground perspective",
    heading_deg: float = 0.0,
    height: int = 480,
) -> "go.Figure":
    """Render a ground-level lunar sky view from real azimuth/elevation data.

    The horizontal axis is a 180-degree field of view centered on ``heading``.
    The terrain line is sampled from the selected site's horizon profile; Sun
    and Earth markers use the current SPICE-derived row.
    """
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")
    i = int(np.clip(current_index, 0, len(df) - 1))
    # unwrap azimuth around the astronaut's heading into [-180, 180].
    az = np.asarray(horizon_profile.azimuth_deg, dtype=float)
    rel = (az - float(heading_deg) + 180.0) % 360.0 - 180.0
    order = np.argsort(rel)
    rel = rel[order]
    terrain = np.asarray(horizon_profile.elevation_deg, dtype=float)[order]
    visible = (rel >= -90.0) & (rel <= 90.0)
    rel, terrain = rel[visible], terrain[visible]

    def relative_body_az(value):
        return (float(value) - float(heading_deg) + 180.0) % 360.0 - 180.0

    sun_x = relative_body_az(df.iloc[i]["sun_az_deg"])
    earth_x = relative_body_az(df.iloc[i]["earth_az_deg"])
    sun_y = float(df.iloc[i]["sun_alt_deg"])
    earth_y = float(df.iloc[i]["earth_alt_deg"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rel, y=terrain, mode="lines", name="Local terrain horizon",
        line=dict(color=COLOR_HORIZON, width=2, dash="dash"),
        fill="tozeroy", fillcolor="rgba(80,95,125,0.25)",
        hovertemplate="Az %{x:.1f}°<br>terrain %{y:+.2f}°<extra></extra>",
    ))
    fig.add_hline(y=0, line_color=COLOR_AXIS, line_width=1,
                  annotation_text="astronomical horizon",
                  annotation_font_color=COLOR_TEXT_MUTED)
    fig.add_trace(go.Scatter(
        x=[sun_x], y=[sun_y], mode="markers+text", name="Sun",
        text=[f"SUN  {sun_y:+.2f}°"], textposition="top center",
        marker=dict(color=COLOR_SUN, size=18, symbol="star",
                    line=dict(color="white", width=1)),
        customdata=[[float(df.iloc[i]["sun_az_deg"]), sun_y]],
        hovertemplate="SUN<br>az %{customdata[0]:.2f}°<br>el %{customdata[1]:+.2f}°<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[earth_x], y=[earth_y], mode="markers+text", name="Earth",
        text=[f"EARTH  {earth_y:+.2f}°"], textposition="top center",
        marker=dict(color=COLOR_EARTH, size=16, symbol="diamond",
                    line=dict(color="white", width=1)),
        customdata=[[float(df.iloc[i]["earth_az_deg"]), earth_y]],
        hovertemplate="EARTH<br>az %{customdata[0]:.2f}°<br>el %{customdata[1]:+.2f}°<extra></extra>",
    ))
    fig.update_xaxes(range=[-90, 90], dtick=30, title="Relative azimuth (°)",
                     gridcolor=COLOR_GRID, zerolinecolor=COLOR_AXIS)
    fig.update_yaxes(range=[-10, 90], dtick=15, title="Elevation (°)",
                     gridcolor=COLOR_GRID, zerolinecolor=COLOR_AXIS)
    fig.update_layout(title=title, hovermode="closest")
    _apply_dark_layout(fig, height=height)
    return fig


def elevation_vs_time_plotly(df: pd.DataFrame,
                             horizon_profile: Optional[horizon.HorizonProfile] = None,
                             title: str = "Altitude vs time",
                             height: int = 600,
                             current_time=None) -> "go.Figure":
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

    if "sun_visible" in df.columns and "earth_visible" in df.columns:
        overlap = df["sun_visible"].astype(bool) & df["earth_visible"].astype(bool)
        start = None
        for i, active in enumerate(overlap.to_numpy()):
            if active and start is None:
                start = i
            if start is not None and (not active or i == len(overlap) - 1):
                end = i if active and i == len(overlap) - 1 else i - 1
                fig.add_vrect(x0=df.iloc[start]["time_utc"], x1=df.iloc[end]["time_utc"],
                              fillcolor="#2dd4a7", opacity=0.10, line_width=0,
                              annotation_text="GOLDEN WINDOW", annotation_position="top left")
                start = None
    if current_time is not None:
        fig.add_vline(x=current_time, line_color="#ff6b8a", line_width=2,
                      annotation_text="CURRENT", annotation_position="top")

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


def comparison_bars_plotly(results: dict, height: int = 380) -> "go.Figure":
    """Grouped horizontal-bar comparison of key metrics across sites.

    `results` is the dict produced in `app.py` of shape
        { site_id: { "site": Site, "df": DataFrame, "summary": Summary, ... } }
    Renders four bars per site (sunlit %, earth visible %, golden window %,
    longest sunlit streak hours normalised to 0-100).
    """
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")

    sites = [v["site"] for v in results.values()]
    names = [s.name for s in sites]
    summaries = [v["summary"] for v in results.values()]

    # Longest streak normalised to 0..100 with a soft cap of 24 hours so
    # very long streaks don't compress the other bars.
    streaks = [min(100.0, s.sunlit_continuous_hours_max / 24.0 * 100.0)
               for s in summaries]

    metrics = [
        ("Sunlit %",          [s.sun_above_real_horizon_pct    for s in summaries], COLOR_SUN),
        ("Earth Comm %",      [s.earth_above_real_horizon_pct for s in summaries], COLOR_EARTH),
        ("Golden Window %",   [s.golden_window_pct            for s in summaries], "#4ade80"),
        ("Max Streak (0-24h)", streaks,                                                "#b794ff"),
    ]

    fig = go.Figure()
    for label, values, color in metrics:
        fig.add_trace(go.Bar(
            y=names,
            x=values,
            name=label,
            orientation="h",
            marker=dict(color=color, line=dict(color="rgba(255,255,255,0.08)", width=1)),
            hovertemplate="<b>%{y}</b><br>" + label + ": %{x:.1f}<extra></extra>",
        ))

    fig.update_layout(
        barmode="group",
        title="Cross-site metric comparison",
        xaxis=dict(title=dict(text="Value", font=dict(color=COLOR_TEXT_MUTED)),
                   tickfont=dict(color=COLOR_TEXT_MUTED),
                   gridcolor=COLOR_GRID, zerolinecolor=COLOR_AXIS,
                   range=[0, 105]),
        yaxis=dict(autorange="reversed", tickfont=dict(color=COLOR_TEXT),
                   gridcolor=COLOR_GRID),
    )
    _apply_dark_layout(fig, height=height)
    return fig


def altitude_strip_plotly(df: pd.DataFrame,
                          horizon_profile: Optional[horizon.HorizonProfile] = None,
                          hours: int = 24,
                          height: int = 320,
                          title: str = "First 24 hours — Sun & Earth altitude") -> "go.Figure":
    """Compact altitude-vs-time strip for the first `hours` hours of the analysis.

    Used in the Site Deep Dive tab to show the daily rhythm in a glance.
    """
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")
    if df.empty:
        fig = go.Figure()
        _apply_dark_layout(fig, height=height)
        return fig

    times = pd.to_datetime(df["time_utc"], utc=True)
    end = times.iloc[0] + pd.Timedelta(hours=hours)
    mask = times <= end
    df_s = df.loc[mask].reset_index(drop=True)
    times_s = times.loc[mask].reset_index(drop=True)

    fig = go.Figure()
    # Terrain fill: above this altitude = visible for the sun
    if horizon_profile is not None and "sun_horizon_deg" in df_s.columns:
        fig.add_trace(go.Scatter(
            x=times_s, y=df_s["sun_horizon_deg"],
            name="Terrain horizon (sun az)",
            line=dict(color=COLOR_HORIZON, width=1, dash="dot"),
            hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=times_s, y=df_s["earth_horizon_deg"],
            name="Terrain horizon (earth az)",
            line=dict(color="rgba(160,180,220,0.35)", width=1, dash="dot"),
            hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=times_s, y=df_s["sun_alt_deg"],
        name="Sun altitude",
        line=dict(color=COLOR_SUN, width=2),
        fill="tozeroy",
        fillcolor="rgba(255,184,69,0.10)",
        hovertemplate="Sun: %{y:+.2f}°<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=times_s, y=df_s["earth_alt_deg"],
        name="Earth altitude",
        line=dict(color=COLOR_EARTH, width=2),
        hovertemplate="Earth: %{y:+.2f}°<extra></extra>",
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(title="", tickfont=dict(color=COLOR_TEXT_MUTED),
                   gridcolor=COLOR_GRID),
        yaxis=dict(title="Altitude (°)", tickfont=dict(color=COLOR_TEXT_MUTED),
                   gridcolor=COLOR_GRID, zerolinecolor=COLOR_AXIS,
                   range=[-5, 90]),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="rgba(18,24,44,0.95)",
                        bordercolor=COLOR_EARTH,
                        font=dict(color=COLOR_TEXT)),
    )
    _apply_dark_layout(fig, height=height)
    return fig


# ---------------------------------------------------------------------------
# Matplotlib (static fallback / small multiples)
# ---------------------------------------------------------------------------

def _mpl_dark_style():
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


def comparison_multi_polar_plotly(results_dict: dict, height: int = 580) -> "go.Figure":
    """Interactive multi-site comparison polar radar.
    Each site's sun track and terrain mask can be compared on a single radar.
    """
    if not _PLOTLY_OK:
        raise RuntimeError("plotly is not installed")

    fig = go.Figure()
    palette = [
        ("#ffb845", "rgba(255, 184, 69, 0.4)"),
        ("#4ea1ff", "rgba(78, 161, 255, 0.4)"),
        ("#2dd4a7", "rgba(45, 212, 167, 0.4)"),
        ("#ff6b8a", "rgba(255, 107, 138, 0.4)"),
        ("#b388ff", "rgba(179, 136, 255, 0.4)"),
        ("#00e5ff", "rgba(0, 229, 255, 0.4)"),
    ]

    for idx, (name, payload) in enumerate(results_dict.items()):
        df = payload["df"]
        prof = payload.get("profile")
        color, _ = palette[idx % len(palette)]

        # Site Sun track
        fig.add_trace(go.Scatterpolar(
            r=90 - df["sun_alt_deg"].clip(lower=-5),
            theta=df["sun_az_deg"],
            mode="lines+markers",
            name=f"{name} (Sun)",
            line=dict(color=color, width=2.2),
            marker=dict(size=4, color=color),
            hovertemplate=f"<b>{name}</b><br>Sun Az: %{{theta:.1f}}°<br>Sun Alt: %{{customdata:.2f}}°<extra></extra>",
            customdata=df["sun_alt_deg"],
        ))

        # Terrain mask
        if prof is not None:
            fig.add_trace(go.Scatterpolar(
                r=90 - np.asarray(prof.elevation_deg),
                theta=np.asarray(prof.azimuth_deg),
                mode="lines",
                name=f"{name} (Horizon)",
                line=dict(color=color, width=1.2, dash="dot"),
                visible="legendonly" if idx > 0 else True,
                hovertemplate=f"<b>{name} Horizon</b><br>Az: %{{theta:.1f}}°<br>Alt: %{{customdata:.2f}}°<extra></extra>",
                customdata=np.asarray(prof.elevation_deg),
            ))

    fig.update_layout(
        polar=dict(
            bgcolor=COLOR_BG,
            radialaxis=dict(
                range=[0, 95],
                tickvals=[0, 30, 60, 90],
                ticktext=["90° (Zenith)", "60°", "30°", "0° (Horizon)"],
                angle=90, tickangle=90,
                gridcolor=COLOR_GRID,
                linecolor=COLOR_AXIS,
                tickfont=dict(color=COLOR_TEXT_MUTED, size=10),
            ),
            angularaxis=dict(
                direction="clockwise",
                rotation=90,
                tickvals=[0, 90, 180, 270],
                ticktext=["N (0°)", "E (90°)", "S (180°)", "W (270°)"],
                gridcolor=COLOR_GRID,
                linecolor=COLOR_AXIS,
                tickfont=dict(color=COLOR_TEXT, size=11),
            ),
        ),
        title="Multi-Site Celestial Overlay — Sun Paths & Local Horizons",
    )
    _apply_dark_layout(fig, height=height)
    return fig
