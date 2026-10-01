"""Lunar Horizon: a focused lunar south-pole mission planning dashboard."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from src import analysis, ephemeris, horizon, plotting, sim, simulator_component, sites


DEFAULT_SITES = [
    "Shackleton-Henson Connecting Ridge",
    "Shackleton Rim (East)",
    "Shackleton Rim (North)",
    "de la Rue",
]

VIEW_OPTIONS = [
    "Overview",
    "Site analysis",
    "Mission simulation",
    "Seasonal sweep",
]


st.set_page_config(
    page_title="Lunar Horizon",
    page_icon=":material/brightness_5:",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def get_cached_site_analysis(
    site_id: str,
    start_iso: str,
    duration_hours: float,
    step_minutes: float,
    include_terrain: bool,
) -> Tuple[pd.DataFrame, analysis.Summary, horizon.HorizonProfile | None]:
    site_obj = sites.get_site(site_id)
    start_dt = datetime.fromisoformat(start_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    profile = (
        horizon.horizon_for_site(
            site_obj.site_id,
            site_obj.lat_deg,
            site_obj.lon_deg,
            site_obj.elev_m,
        )
        if include_terrain
        else None
    )
    df, summary = analysis.analyze(
        site=site_obj,
        start_utc=start_dt,
        duration_hours=duration_hours,
        step_minutes=step_minutes,
        profile=profile,
        include_dem_mask=include_terrain,
    )
    return df, summary, profile


@st.cache_data(show_spinner=False)
def get_cached_mission_plan(
    site_id: str,
    launch_iso: str,
    transit_days: float,
    surface_days: float,
    step_minutes: float,
) -> dict:
    site_obj = sites.get_site(site_id)
    launch_dt = datetime.fromisoformat(launch_iso)
    if launch_dt.tzinfo is None:
        launch_dt = launch_dt.replace(tzinfo=timezone.utc)
    plan = sim.plan_mission(
        site=site_obj,
        launch_utc=launch_dt,
        transit_days=transit_days,
        surface_days=surface_days,
        step_minutes=step_minutes,
    )
    return sim.plan_to_dict(plan)


@st.cache_data(show_spinner=False)
def get_cached_date_sweep(
    site_id: str,
    start_iso: str,
    n_dates: int,
    include_terrain: bool,
) -> pd.DataFrame:
    site_obj = sites.get_site(site_id)
    start_dt = datetime.fromisoformat(start_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    return analysis.date_sweep(
        site=site_obj,
        start_date_utc=start_dt,
        n_dates=int(n_dates),
        duration_hours=24.0,
        step_minutes=15.0,
        include_dem_mask=include_terrain,
    )


def _default_settings() -> dict:
    return {
        "sites": DEFAULT_SITES.copy(),
        "start_date": date(2026, 11, 1),
        "duration_days": 5,
        "step_minutes": 15,
        "include_terrain": True,
    }


def _render_sidebar(all_site_objs: List[sites.Site]) -> dict:
    if "mission_settings" not in st.session_state:
        st.session_state["mission_settings"] = _default_settings()

    settings = st.session_state["mission_settings"]
    site_names = [site.name for site in all_site_objs]

    with st.sidebar:
        st.header("Mission settings")
        st.caption("Set the analysis inputs, then apply them once.")

        with st.form("mission_settings_form", border=False):
            selected_names = st.multiselect(
                "Landing sites",
                options=site_names,
                default=settings["sites"],
                help="Choose one or more candidate sites to compare.",
            )
            start_date = st.date_input(
                "Mission start date (UTC)",
                value=settings["start_date"],
            )
            duration_days = st.slider(
                "Analysis window (days)",
                min_value=1,
                max_value=30,
                value=int(settings["duration_days"]),
            )
            step_minutes = st.select_slider(
                "Time resolution",
                options=[1, 5, 10, 15, 30, 60],
                value=int(settings["step_minutes"]),
                format_func=lambda value: f"{value} min",
            )
            include_terrain = st.checkbox(
                "Apply terrain horizon",
                value=bool(settings["include_terrain"]),
                help="Use a site horizon profile instead of a flat geometric horizon.",
            )
            apply_settings = st.form_submit_button(
                "Apply settings",
                type="primary",
                width="stretch",
            )

        if apply_settings:
            settings = {
                "sites": selected_names,
                "start_date": start_date,
                "duration_days": duration_days,
                "step_minutes": step_minutes,
                "include_terrain": include_terrain,
            }
            st.session_state["mission_settings"] = settings

        if st.button("Reset settings", width="stretch"):
            st.session_state["mission_settings"] = _default_settings()
            st.rerun()

        backend = "SPICE · JPL" if ephemeris.using_spice() else "Analytic fallback"
        st.caption(f"Ephemeris backend: {backend}")

    return settings


def _terrain_label(results: Dict[str, dict], include_terrain: bool) -> str:
    if not include_terrain:
        return "geometric horizon"
    sources = {
        payload["profile"].source
        for payload in results.values()
        if payload["profile"] is not None
    }
    if sources == {"dem"}:
        return "LOLA DEM terrain"
    if sources == {"synthetic"}:
        return "synthetic terrain model"
    return "mixed terrain profiles"


def _comparison_table(results: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for payload in results.values():
        site = payload["site"]
        summary = payload["summary"]
        rows.append(
            {
                "Site": site.name,
                "Region": site.region.replace("_", " ").title(),
                "Sunlit": f"{summary.sun_above_real_horizon_pct:.1f}%",
                "Earth visible": f"{summary.earth_above_real_horizon_pct:.1f}%",
                "Golden window": f"{summary.golden_window_pct:.1f}%",
                "Sun streak": f"{summary.sunlit_continuous_hours_max:.1f} h",
                "Earth blackout": f"{summary.earth_blackout_minutes:.0f} min",
            }
        )
    return pd.DataFrame(rows)


def _render_overview(
    results: Dict[str, dict],
    start_date: date,
    duration_days: int,
    terrain_label: str,
) -> None:
    st.title("Lunar Horizon", anchor=False)
    st.caption(
        "Compare lunar south-pole sites for sunlight, direct-to-Earth communication, "
        "and mission timing."
    )
    st.caption(f"Window: {start_date.isoformat()} · {duration_days} days · {terrain_label}")

    best_sun = max(results.values(), key=lambda item: item["summary"].sun_above_real_horizon_pct)
    best_earth = max(results.values(), key=lambda item: item["summary"].earth_above_real_horizon_pct)
    best_golden = max(results.values(), key=lambda item: item["summary"].golden_window_pct)
    best_streak = max(results.values(), key=lambda item: item["summary"].sunlit_continuous_hours_max)

    metric_cols = st.columns(4)
    metric_cols[0].metric(
        "Best sunlight",
        f"{best_sun['summary'].sun_above_real_horizon_pct:.1f}%",
        best_sun["site"].name,
    )
    metric_cols[1].metric(
        "Best Earth visibility",
        f"{best_earth['summary'].earth_above_real_horizon_pct:.1f}%",
        best_earth["site"].name,
    )
    metric_cols[2].metric(
        "Best golden window",
        f"{best_golden['summary'].golden_window_pct:.1f}%",
        best_golden["site"].name,
    )
    metric_cols[3].metric(
        "Longest sun streak",
        f"{best_streak['summary'].sunlit_continuous_hours_max:.1f} h",
        best_streak["site"].name,
    )

    st.subheader("Site comparison")
    comparison_df = _comparison_table(results)
    st.dataframe(comparison_df, width="stretch", hide_index=True)
    st.download_button(
        "Download comparison CSV",
        comparison_df.to_csv(index=False).encode("utf-8"),
        file_name=f"lunar_comparison_{start_date.isoformat()}.csv",
        mime="text/csv",
        width="content",
    )

    st.subheader("At-a-glance chart")
    st.plotly_chart(
        plotting.comparison_bars_plotly(results, height=380),
        width="stretch",
    )


def _format_windows(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty:
        return windows
    formatted = windows.copy()
    formatted["start_utc"] = formatted["start_utc"].dt.strftime("%Y-%m-%d %H:%M UTC")
    formatted["end_utc"] = formatted["end_utc"].dt.strftime("%Y-%m-%d %H:%M UTC")
    formatted["duration_hours"] = formatted["duration_hours"].map(lambda value: f"{value:.2f} h")
    formatted["min_sun_elevation_deg"] = formatted["min_sun_elevation_deg"].map(lambda value: f"{value:+.2f}°")
    formatted["min_earth_elevation_deg"] = formatted["min_earth_elevation_deg"].map(lambda value: f"{value:+.2f}°")
    formatted.columns = ["Start UTC", "End UTC", "Duration", "Min Sun altitude", "Min Earth altitude"]
    return formatted


def _render_site_analysis(
    selected_sites: List[sites.Site],
    results: Dict[str, dict],
    start_date: date,
    include_terrain: bool,
) -> None:
    st.header("Site analysis")
    site_id = st.selectbox(
        "Site",
        options=[site.site_id for site in selected_sites],
        format_func=lambda value: sites.get_site(value).name,
        key="analysis_site_id",
    )
    payload = results[site_id]
    site = payload["site"]
    df = payload["df"]
    summary = payload["summary"]
    profile = payload["profile"]

    st.caption(site.description)
    metric_cols = st.columns(5)
    metric_cols[0].metric("Sunlit", f"{summary.sun_above_real_horizon_pct:.1f}%")
    metric_cols[1].metric("Sun streak", f"{summary.sunlit_continuous_hours_max:.1f} h")
    metric_cols[2].metric("Earth visible", f"{summary.earth_above_real_horizon_pct:.1f}%")
    metric_cols[3].metric("Earth blackout", f"{summary.earth_blackout_minutes:.0f} min")
    metric_cols[4].metric("Golden window", f"{summary.golden_window_pct:.1f}%")

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(
            plotting.sky_polar_plotly(
                df,
                title=f"Sky track · {site.name}",
                horizon_profile=profile,
                height=500,
            ),
            width="stretch",
        )
    with chart_cols[1]:
        st.plotly_chart(
            plotting.elevation_vs_time_plotly(
                df,
                horizon_profile=profile,
                title="Altitude over time",
                height=500,
            ),
            width="stretch",
        )

    st.subheader("Golden windows")
    windows = analysis.golden_windows(df)
    if windows.empty:
        st.info("No simultaneous Sun and Earth visibility in this analysis window.")
    else:
        display_windows = _format_windows(windows)
        st.dataframe(display_windows, width="stretch", hide_index=True)
        st.download_button(
            "Download golden windows",
            display_windows.to_csv(index=False).encode("utf-8"),
            file_name=f"{site.site_id}_golden_windows.csv",
            mime="text/csv",
            width="content",
        )

    with st.expander("Advanced: search future golden windows"):
        with st.form("golden_window_search_form", border=False):
            search_start = st.date_input("Search start date (UTC)", value=start_date)
            search_span = st.slider("Scan span (days)", 7, 45, 21)
            min_overlap = st.number_input(
                "Minimum overlap (hours)",
                min_value=0.5,
                max_value=72.0,
                value=2.0,
                step=0.5,
                format="%.1f",
            )
            run_search = st.form_submit_button("Search windows", width="content")

        if run_search:
            found_windows: List[dict] = []
            search_start_dt = datetime.combine(
                search_start,
                datetime.min.time(),
            ).replace(tzinfo=timezone.utc)
            search_profile = horizon.horizon_for_site(
                site.site_id,
                site.lat_deg,
                site.lon_deg,
                site.elev_m,
            ) if include_terrain else None

            with st.spinner("Scanning mission windows…"):
                for day_index in range(int(search_span)):
                    day_start = search_start_dt + timedelta(days=day_index)
                    day_df, _ = analysis.analyze(
                        site=site,
                        start_utc=day_start,
                        duration_hours=24.0,
                        step_minutes=15.0,
                        profile=search_profile,
                        include_dem_mask=include_terrain,
                    )
                    day_windows = analysis.golden_windows(day_df)
                    for _, row in day_windows.iterrows():
                        duration = float(row["duration_hours"])
                        if duration >= float(min_overlap):
                            found_windows.append(
                                {
                                    "Date": day_start.strftime("%Y-%m-%d"),
                                    "Start UTC": row["start_utc"].strftime("%Y-%m-%d %H:%M"),
                                    "End UTC": row["end_utc"].strftime("%Y-%m-%d %H:%M"),
                                    "Duration": f"{duration:.2f} h",
                                }
                            )
            st.session_state["clean_search_results"] = found_windows

        if "clean_search_results" in st.session_state:
            search_results = st.session_state["clean_search_results"]
            if search_results:
                search_df = pd.DataFrame(search_results)
                st.success(f"Found {len(search_df)} qualifying windows.")
                st.dataframe(search_df, width="stretch", hide_index=True)
            else:
                st.info("No qualifying windows found for the selected range.")

    with st.expander("Raw telemetry"):
        st.dataframe(df.head(200), width="stretch", hide_index=True)
        st.download_button(
            "Download full telemetry",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{site.site_id}_telemetry.csv",
            mime="text/csv",
            width="content",
        )


def _render_mission_simulation(
    selected_sites: List[sites.Site],
    duration_days: int,
    start_date: date,
) -> None:
    st.header("Mission simulation")
    st.caption("Explore the launch, transit, descent, and surface-operations sequence.")

    controls = st.columns(4)
    with controls[0]:
        sim_site_id = st.selectbox(
            "Landing site",
            options=[site.site_id for site in selected_sites],
            format_func=lambda value: sites.get_site(value).name,
            key="simulation_site_id",
        )
    with controls[1]:
        launch_date = st.date_input(
            "Launch date (UTC)",
            value=start_date - timedelta(days=3),
            key="simulation_launch_date",
        )
    with controls[2]:
        transit_days = st.slider(
            "Transit (days)",
            min_value=1,
            max_value=5,
            value=3,
            key="simulation_transit_days",
        )
    with controls[3]:
        resolution = st.selectbox(
            "Resolution",
            options=[10, 15, 30],
            index=1,
            format_func=lambda value: f"{value} min",
            key="simulation_resolution",
        )

    launch_dt = datetime.combine(launch_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    landing_dt = launch_dt + timedelta(days=int(transit_days))
    plan_data = get_cached_mission_plan(
        sim_site_id,
        launch_dt.isoformat(),
        float(transit_days),
        float(duration_days),
        float(resolution),
    )

    summary_cols = st.columns(3)
    summary_cols[0].metric("Launch", launch_dt.strftime("%Y-%m-%d"))
    summary_cols[1].metric("Landing", landing_dt.strftime("%Y-%m-%d"))
    summary_cols[2].metric("Surface operations", f"{duration_days} days")

    simulator_html = simulator_component.get_simulator_html(plan_data, height=750)
    simulator_src = (
        "data:text/html;base64,"
        + base64.b64encode(simulator_html.encode("utf-8")).decode("ascii")
    )
    st.iframe(simulator_src, height=760, width="stretch")

    surface = plan_data.get("surface", {})
    if surface.get("sun_alt"):
        index = len(surface["sun_alt"]) // 2
        telemetry = pd.DataFrame(
            {
                "Metric": ["Sun altitude", "Earth altitude", "Sun horizon", "Earth horizon"],
                "Value": [
                    f"{surface['sun_alt'][index]:+.2f}°",
                    f"{surface['earth_alt'][index]:+.2f}°",
                    f"{surface['horizon_sun'][index]:+.2f}°",
                    f"{surface['horizon_earth'][index]:+.2f}°",
                ],
            }
        )
        with st.expander("Mid-surface telemetry snapshot"):
            st.dataframe(telemetry, width="stretch", hide_index=True)


def _render_seasonal_sweep(
    selected_sites: List[sites.Site],
    results: Dict[str, dict],
    start_dt: datetime,
    include_terrain: bool,
) -> None:
    st.header("Seasonal sweep")
    st.caption("Sample visibility and sunlight across roughly one lunar year.")

    controls = st.columns(2)
    with controls[0]:
        metric = st.selectbox(
            "Metric",
            options=[
                "sun_above_real_horizon_pct",
                "sun_max_altitude_deg",
                "sunlit_continuous_hours_max",
                "earth_above_real_horizon_pct",
                "earth_min_altitude_deg",
                "earth_blackout_minutes",
            ],
            format_func=lambda value: {
                "sun_above_real_horizon_pct": "Sunlit time",
                "sun_max_altitude_deg": "Maximum Sun altitude",
                "sunlit_continuous_hours_max": "Longest Sun streak",
                "earth_above_real_horizon_pct": "Earth visibility",
                "earth_min_altitude_deg": "Minimum Earth altitude",
                "earth_blackout_minutes": "Earth blackout",
            }[value],
        )
    with controls[1]:
        n_dates = st.slider(
            "Sample dates",
            min_value=4,
            max_value=24,
            value=12,
            step=2,
        )

    with st.spinner("Computing seasonal sweep…"):
        sweep_data = {
            payload["site"].name: get_cached_date_sweep(
                payload["site"].site_id,
                start_dt.isoformat(),
                n_dates,
                include_terrain,
            )
            for payload in results.values()
        }

    titles = {
        "sun_above_real_horizon_pct": "Sunlit time",
        "sun_max_altitude_deg": "Maximum Sun altitude",
        "sunlit_continuous_hours_max": "Longest Sun streak",
        "earth_above_real_horizon_pct": "Earth visibility",
        "earth_min_altitude_deg": "Minimum Earth altitude",
        "earth_blackout_minutes": "Earth blackout",
    }
    st.plotly_chart(
        plotting.date_sweep_heatmap_plotly(
            sweep_data,
            metric=metric,
            title=f"{titles[metric]} across the lunar year",
        ),
        width="stretch",
    )


all_site_objs = sites.all_sites()
settings = _render_sidebar(all_site_objs)
selected_names = settings["sites"]

if not selected_names:
    st.warning("Select at least one landing site in the sidebar, then apply settings.")
    st.stop()

site_map = {site.name: site for site in all_site_objs}
selected_sites = [site_map[name] for name in selected_names]
start_date = settings["start_date"]
duration_days = int(settings["duration_days"])
step_minutes = float(settings["step_minutes"])
include_terrain = bool(settings["include_terrain"])
start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)

with st.spinner("Computing site analysis…"):
    results: Dict[str, dict] = {}
    for site in selected_sites:
        df, summary, profile = get_cached_site_analysis(
            site.site_id,
            start_dt.isoformat(),
            float(duration_days * 24),
            step_minutes,
            include_terrain,
        )
        results[site.site_id] = {
            "site": site,
            "df": df,
            "summary": summary,
            "profile": profile,
        }

terrain_label = _terrain_label(results, include_terrain)
if include_terrain and terrain_label == "synthetic terrain model":
    st.warning(
        "Synthetic terrain profiles are active. Use site-specific LOLA horizon profiles "
        "for survey-grade visibility results."
    )

view = st.segmented_control(
    "Workspace",
    options=VIEW_OPTIONS,
    default="Overview",
    key="workspace_view",
    width="stretch",
)

if view == "Overview":
    _render_overview(results, start_date, duration_days, terrain_label)
elif view == "Site analysis":
    _render_site_analysis(selected_sites, results, start_date, include_terrain)
elif view == "Mission simulation":
    _render_mission_simulation(selected_sites, duration_days, start_date)
elif view == "Seasonal sweep":
    _render_seasonal_sweep(selected_sites, results, start_dt, include_terrain)

st.caption(
    f"{len(selected_sites)} site(s) · {duration_days}-day window · "
    f"{terrain_label} · {('SPICE · JPL' if ephemeris.using_spice() else 'analytic fallback')}"
)
