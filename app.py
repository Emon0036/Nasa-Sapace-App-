"""
Lunar Horizon — Streamlit application.

Run:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import datetime, time as time_value, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src import analysis, ephemeris, horizon, plotting, recommender, sites, sim


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Lunar Horizon — South Pole Mission Planner",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject the dark "space" theme
_THEME_CSS = Path(__file__).resolve().parent / "assets" / "theme.css"
if _THEME_CSS.exists():
    st.markdown(f"<style>{_THEME_CSS.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------

def render_hero(backend_label: str) -> None:
    st.markdown(
        f"""
        <div class="lh-hero">
          <div class="lh-title">Lunar Horizon</div>
          <div class="lh-subtitle">
            Mission planning for the Moon's south pole — solar power &
            direct-to-Earth communication windows, visualized.
          </div>
          <div style="margin-top:.7rem">
            <span class="lh-chip">☀ Sun tracking</span>
            <span class="lh-chip">🌐 Earth visibility</span>
            <span class="lh-chip">⛰ Terrain horizon</span>
            <span class="lh-chip">📅 Date sweep</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_card(label: str, value: str, kind: str = "") -> str:
    cls = f"lh-kpi {kind}".strip()
    return (
        f"<div class='{cls}'>"
        f"<div class='lh-kpi-value'>{value}</div>"
        f"<div class='lh-kpi-label'>{label}</div>"
        f"</div>"
    )


def render_kpi_row(kpis: list[tuple[str, str, str]]) -> None:
    """kpis: list of (label, value, kind)."""
    cols = st.columns(len(kpis))
    for col, (label, value, kind) in zip(cols, kpis):
        col.markdown(kpi_card(label, value, kind), unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _rank_scenarios_cached(site_rows, start_iso: str, duration_hours: float,
                           model_modified_ns: int) -> pd.DataFrame:
    del model_modified_ns  # Include the artifact timestamp in the cache key.
    site_objects = [sites.Site(*row) for row in site_rows]
    return recommender.rank_scenarios(
        site_objects,
        datetime.fromisoformat(start_iso),
        duration_hours,
        delays_hours=(0, 24, 48),
        sample_hours=3.0,
    )


@st.cache_data(show_spinner=False)
def _verify_scenario_cached(site_row, start_iso: str, duration_hours: float,
                            step_minutes: float, include_profile: bool):
    site = sites.Site(*site_row)
    profile = horizon.horizon_for_site(site.site_id, site.lat_deg, site.lon_deg, site.elev_m)
    frame, summary = analysis.analyze(
        site=site,
        start_utc=datetime.fromisoformat(start_iso),
        duration_hours=duration_hours,
        step_minutes=step_minutes,
        profile=profile,
        include_dem_mask=include_profile,
    )
    return frame, summary, profile


@st.cache_data(show_spinner=False)
def _date_sweep_cached(site_row, start_iso: str, n_dates: int) -> pd.DataFrame:
    site = sites.Site(*site_row)
    return analysis.date_sweep(
        site,
        start_date_utc=datetime.fromisoformat(start_iso),
        n_dates=n_dates,
        duration_hours=24.0,
        step_minutes=360.0,
    )


# ---------------------------------------------------------------------------
# Sidebar — inputs
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### ⚙ Mission parameters")

    all_sites = sites.all_sites()
    site_options = {s.name: s for s in all_sites}
    selected_names = st.multiselect(
        "Landing sites",
        options=list(site_options.keys()),
        default=["Shackleton-Henson Connecting Ridge",
                 "Shackleton Rim (North)",
                 "de la Rue",
                 "Flat Reference (no terrain)"],
        help="Pick 1–6 sites to compare.",
    )

    add_custom_site = st.checkbox("Add custom coordinate site", value=False)
    custom_lat = custom_lon = custom_elev = None
    if add_custom_site:
        custom_lat = st.number_input("Custom latitude (°)", min_value=-90.0, max_value=90.0,
                                     value=-89.5, step=0.01)
        custom_lon = st.number_input("Custom east longitude (°)", min_value=-180.0, max_value=180.0,
                                     value=0.0, step=0.1)
        custom_elev = st.number_input("Custom elevation (m)", min_value=-12000.0, max_value=12000.0,
                                      value=0.0, step=10.0)

    start_date = st.date_input(
        "Start date (UTC)",
        value=datetime(2026, 6, 1).date(),
    )
    start_time = st.time_input("Start time (UTC)", value=time_value(0, 0))
    duration_days = st.slider(
        "Observation duration (24-hour days)",
        min_value=1, max_value=30, value=5, step=1,
    )
    step_minutes = st.select_slider(
        "Time resolution (min)",
        options=[1, 5, 10, 15, 30, 60],
        value=10,
    )
    include_terrain = st.checkbox(
        "Use measured DEM horizon, if installed",
        value=False,
        help="No LOLA DEM is currently bundled. Synthetic profiles remain display-only and are not used as visibility masks.",
    )

    st.divider()
    backend_label, backend_note = ephemeris.backend_status()
    st.markdown("### 🛰 Backend")
    st.info(f"Running with **{backend_label}**")
    st.caption(backend_note)
    st.caption("Site coordinates are nominal prototype points. Survey-grade landing coordinates and LOLA terrain are not included.")


# ---------------------------------------------------------------------------
# Hero + landing
# ---------------------------------------------------------------------------

render_hero(backend_label)

if not selected_names and not add_custom_site:
    st.warning("Pick at least one site in the sidebar.")
    st.stop()

selected_sites = [site_options[n] for n in selected_names]
if add_custom_site:
    selected_sites.append(sites.Site(
        site_id="custom_site",
        name="Custom coordinate site",
        lat_deg=float(custom_lat),
        lon_deg=float(custom_lon),
        elev_m=float(custom_elev),
        description="User-entered lunar geodetic coordinates.",
        region="custom",
    ))

start_dt = datetime.combine(start_date, start_time).replace(tzinfo=timezone.utc)
duration_hours = duration_days * 24.0
result_signature = (
    tuple(site.site_id for site in selected_sites),
    start_dt.isoformat(),
    float(duration_hours),
    float(step_minutes),
    bool(include_terrain),
)


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

sample_count = int(duration_hours * 60.0 / float(step_minutes)) + 1
too_many_samples = sample_count > 5000
if too_many_samples:
    st.warning("This cadence exceeds the 5,000-sample limit per Horizons query. Increase the time step or shorten the duration.")
compute = st.button("Compute visibility", type="primary", width="stretch", disabled=too_many_samples)

if "results" not in st.session_state:
    st.session_state.results = None

if compute:
    progress = st.progress(0.0, text="Computing…")

    results = {}
    try:
        for i, s in enumerate(selected_sites):
            progress.progress(i / max(1, len(selected_sites)),
                              text=f"Computing {s.name}…")
            prof = (horizon.horizon_for_site(s.site_id, s.lat_deg, s.lon_deg, s.elev_m)
                    if include_terrain else None)
            df, summary = analysis.analyze(
                site=s,
                start_utc=start_dt,
                duration_hours=duration_hours,
                step_minutes=float(step_minutes),
                profile=prof,
                include_dem_mask=include_terrain,
            )
            results[s.site_id] = {"site": s, "df": df, "summary": summary, "profile": prof}
        progress.progress(1.0, text="Done.")
        st.session_state.results = results
        st.session_state.result_signature = result_signature
    except Exception as exc:
        st.session_state.results = None
        st.session_state.result_signature = None
        st.error(f"Visibility calculation failed: {exc}")

results = st.session_state.results

if results is None:
    st.markdown(
        """
        <div class="lh-card" style="text-align:center; padding:2rem">
          <div style="font-size:1.1rem; color:var(--text-muted)">
            Adjust parameters in the sidebar, then press
            <b style="color:var(--text)">Compute visibility</b> to begin.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

if st.session_state.get("result_signature") != result_signature:
    st.info("Mission inputs changed. Press **Compute visibility** to refresh the results.")
    st.stop()


# ---------------------------------------------------------------------------
# Headline KPIs (aggregate across selected sites)
# ---------------------------------------------------------------------------

st.markdown("### 📊 Mission overview")

best_sun = max(results.values(), key=lambda v: v["summary"].sun_above_real_horizon_pct)
best_earth = max(results.values(), key=lambda v: v["summary"].earth_above_real_horizon_pct)

render_kpi_row([
    ("Sites analyzed",           str(len(results)),                          ""),
    ("Best sunlit",              f"{best_sun['summary'].sun_above_real_horizon_pct:.1f}%", "sun"),
    ("Most Earth-visible",       f"{best_earth['summary'].earth_above_real_horizon_pct:.1f}%", "earth"),
    ("Max sunlit streak",        f"{max(v['summary'].sunlit_continuous_hours_max for v in results.values()):.1f} h", "streak"),
    ("Max Earth blackout",       f"{max(v['summary'].earth_blackout_minutes for v in results.values()):.0f} min", "blackout"),
])


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

st.markdown("### 🗂 Comparison table")

sum_df = pd.DataFrame([{
    "Site": v["site"].name,
    "Region": v["site"].region.replace("_", " ").title(),
    "Lat": f"{v['site'].lat_deg:.2f}°",
    "Lon": f"{v['site'].lon_deg:.1f}°",
    "Sun > 0°": f"{v['summary'].sun_above_horizon_pct:.1f}%",
    "Sun > selected profile": f"{v['summary'].sun_above_real_horizon_pct:.1f}%",
    "Max sunlit (h)": f"{v['summary'].sunlit_continuous_hours_max:.1f}",
    "Max sun alt": f"{v['summary'].sun_max_altitude_deg:.2f}°",
    "Earth > 0°": f"{v['summary'].earth_above_horizon_pct:.1f}%",
    "Earth > selected profile": f"{v['summary'].earth_above_real_horizon_pct:.1f}%",
    "Max blackout (min)": f"{v['summary'].earth_blackout_minutes:.0f}",
} for v in results.values()])

st.dataframe(sum_df, hide_index=True, alt="Landing site comparison summary")


# ---------------------------------------------------------------------------
# Explainable ML recommendation and physical verification
# ---------------------------------------------------------------------------

st.markdown("### ML-assisted scenario ranking")
st.caption(
    "A random-forest surrogate trained on JPL Horizons ephemerides ranks the selected sites "
    "at the chosen start and 24/48-hour delays. The score is 60% predicted sunlight plus "
    "40% predicted Earth visibility. The top three scenarios are recomputed with the physical "
    "ephemeris source and selected using the same score."
)

site_rows = tuple((
    s.site_id, s.name, s.lat_deg, s.lon_deg, s.elev_m, s.description, s.region,
) for s in selected_sites)
try:
    model_modified_ns = (
        recommender.MODEL_PATH.stat().st_mtime_ns if recommender.MODEL_PATH.exists() else 0
    )
    scenarios = _rank_scenarios_cached(
        site_rows, start_dt.isoformat(), duration_hours, model_modified_ns)
    excluded_from_model = scenarios.attrs.get("excluded_sites", [])
    if excluded_from_model:
        st.warning(
            "ML ranking omitted sites more than 5° from sampled coordinates: "
            + ", ".join(excluded_from_model)
            + ". Their physical ephemeris results remain in the comparison above."
        )
    display_columns = [
        "rank", "site_name", "delay_hours", "sun_above_geometric_horizon_pct",
        "earth_above_geometric_horizon_pct", "max_sunlit_streak_h",
        "max_earth_blackout_min", "score", "explanation",
    ]
    st.dataframe(
        scenarios[display_columns].head(10),
        hide_index=True,
        alt="Machine-learning scenario rankings and score explanations",
    )

    shortlist = scenarios.head(3)
    physical_candidates = []
    with st.spinner("Checking the top three ML scenarios with the physical ephemeris source…"):
        for _, candidate in shortlist.iterrows():
            candidate_site = next(s for s in selected_sites if s.site_id == candidate["site_id"])
            candidate_start = datetime.fromisoformat(str(candidate["start_utc"]))
            candidate_profile = horizon.horizon_for_site(
                candidate_site.site_id, candidate_site.lat_deg,
                candidate_site.lon_deg, candidate_site.elev_m)
            use_measured_profile = bool(include_terrain and candidate_profile.source == "dem")
            _, candidate_summary, candidate_profile = _verify_scenario_cached(
                (candidate_site.site_id, candidate_site.name, candidate_site.lat_deg,
                 candidate_site.lon_deg, candidate_site.elev_m,
                 candidate_site.description, candidate_site.region),
                candidate_start.isoformat(),
                duration_hours,
                float(step_minutes),
                use_measured_profile,
            )
            physical_score = (
                recommender.MISSION_SCORE_WEIGHTS["sunlight"] * candidate_summary.sun_above_real_horizon_pct
                + recommender.MISSION_SCORE_WEIGHTS["earth_visibility"] * candidate_summary.earth_above_real_horizon_pct
            )
            physical_candidates.append({
                "candidate": candidate,
                "site": candidate_site,
                "summary": candidate_summary,
                "profile": candidate_profile,
                "uses_measured_profile": use_measured_profile,
                "physical_score": float(physical_score),
            })

    physical_candidates.sort(
        key=lambda item: (
            item["physical_score"],
            float(item["candidate"]["score"]),
            -float(item["candidate"]["delay_hours"]),
        ),
        reverse=True,
    )
    verification_table = pd.DataFrame([{
        "ML rank": int(item["candidate"]["rank"]),
        "Site": item["site"].name,
        "Delay (h)": int(item["candidate"]["delay_hours"]),
        "ML score": float(item["candidate"]["score"]),
        "Physical Sun visible (%)": item["summary"].sun_above_real_horizon_pct,
        "Physical Earth visible (%)": item["summary"].earth_above_real_horizon_pct,
        "Physical score": item["physical_score"],
    } for item in physical_candidates])
    st.dataframe(
        verification_table,
        hide_index=True,
        alt="Physical re-ranking of the three highest machine-learning scenarios",
    )

    selected_candidate = physical_candidates[0]
    winner = selected_candidate["candidate"]
    winner_site = selected_candidate["site"]
    verified = selected_candidate["summary"]
    verified_profile = selected_candidate["profile"]
    winner_uses_measured_profile = selected_candidate["uses_measured_profile"]
    st.success(
        f"Physically confirmed recommendation among the top three ML candidates: "
        f"{winner_site.name}, delayed {int(winner['delay_hours'])} h. "
        f"Source: {verified.backend}."
    )
    horizon_basis = f"{verified_profile.source} DEM horizon profile" if winner_uses_measured_profile else "geometric horizon; synthetic terrain excluded"
    st.caption(
        f"Physical score {selected_candidate['physical_score']:.1f}/100. "
        f"Sun visible {verified.sun_above_real_horizon_pct:.1f}%; "
        f"Earth visible {verified.earth_above_real_horizon_pct:.1f}%; basis: {horizon_basis}."
    )
    physical_vs_ml = pd.DataFrame([
        {
            "Condition": "Sun visible",
            "ML estimate (%)": float(winner["sun_above_geometric_horizon_pct"]),
            "Physical check (%)": verified.sun_above_real_horizon_pct,
            "Physical minus ML (percentage points)": verified.sun_above_real_horizon_pct - float(winner["sun_above_geometric_horizon_pct"]),
        },
        {
            "Condition": "Earth visible",
            "ML estimate (%)": float(winner["earth_above_geometric_horizon_pct"]),
            "Physical check (%)": verified.earth_above_real_horizon_pct,
            "Physical minus ML (percentage points)": verified.earth_above_real_horizon_pct - float(winner["earth_above_geometric_horizon_pct"]),
        },
    ])
    st.dataframe(
        physical_vs_ml,
        hide_index=True,
        alt="Machine-learning estimates compared with the physical check for the recommended scenario",
    )
    st.caption("Near-horizon visibility can change with small altitude errors; the physical time series is the confirmation for this prototype.")

    baseline_site = selected_sites[0]
    baseline_profile = horizon.horizon_for_site(
        baseline_site.site_id, baseline_site.lat_deg, baseline_site.lon_deg, baseline_site.elev_m)
    baseline_uses_measured_profile = bool(include_terrain and baseline_profile.source == "dem")
    _, baseline, _ = _verify_scenario_cached(
        (baseline_site.site_id, baseline_site.name, baseline_site.lat_deg,
         baseline_site.lon_deg, baseline_site.elev_m, baseline_site.description,
         baseline_site.region),
        start_dt.isoformat(),
        duration_hours,
        float(step_minutes),
        baseline_uses_measured_profile,
    )
    comparison = pd.DataFrame([
        {
            "Scenario": "A · selected baseline",
            "Site": baseline_site.name,
            "Start (UTC)": baseline.start_utc.isoformat(),
            "Sun visible (%)": baseline.sun_above_real_horizon_pct,
            "Earth visible (%)": baseline.earth_above_real_horizon_pct,
            "Longest sunlit run (h)": baseline.sunlit_continuous_hours_max,
            "Longest Earth blackout (min)": baseline.earth_blackout_minutes,
            "Source": baseline.backend,
        },
        {
            "Scenario": "B · ML recommendation, physically checked",
            "Site": winner_site.name,
            "Start (UTC)": verified.start_utc.isoformat(),
            "Sun visible (%)": verified.sun_above_real_horizon_pct,
            "Earth visible (%)": verified.earth_above_real_horizon_pct,
            "Longest sunlit run (h)": verified.sunlit_continuous_hours_max,
            "Longest Earth blackout (min)": verified.earth_blackout_minutes,
            "Source": verified.backend,
        },
    ])
    st.dataframe(comparison, hide_index=True, alt="Physical comparison of the baseline and recommended mission scenarios")
    if winner_uses_measured_profile and baseline_uses_measured_profile:
        comparison_basis = "Both rows apply site-specific measured DEM horizons."
    elif not winner_uses_measured_profile and not baseline_uses_measured_profile:
        comparison_basis = "Both rows use the geometric horizon; synthetic profiles are excluded."
    else:
        comparison_basis = (
            f"Horizon bases differ: baseline={baseline_profile.source}, "
            f"recommendation={winner_profile.source}."
        )
    st.caption(comparison_basis)
except Exception as exc:
    st.warning(f"ML recommendation is unavailable: {exc}")


# ---------------------------------------------------------------------------
# Per-site deep dive
# ---------------------------------------------------------------------------

st.markdown("### 🔭 Per-site deep dive")

tabs = st.tabs([v["site"].name for v in results.values()])

for tab, (sid, payload) in zip(tabs, results.items()):
    site = payload["site"]
    df = payload["df"]
    summary = payload["summary"]
    prof = payload["profile"]

    with tab:
        st.markdown(
            f"<div style='color:var(--text-muted); margin-bottom:.6rem'>"
            f"{site.description}</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            "Visibility uses a processed DEM horizon."
            if prof is not None and prof.source == "dem"
            else "Visibility uses the geometric horizon. Any displayed synthetic profile is illustrative only and is not applied."
            if prof is not None
            else "Visibility uses the geometric horizon; no terrain mask was applied."
        )

        render_kpi_row([
            ("Sun above active horizon", f"{summary.sun_above_real_horizon_pct:.1f}%", "sun"),
            ("Max sunlit streak", f"{summary.sunlit_continuous_hours_max:.1f} h", "streak"),
            ("Earth visible",     f"{summary.earth_above_real_horizon_pct:.1f}%", "earth"),
            ("Max Earth blackout",f"{summary.earth_blackout_minutes:.0f} min", "blackout"),
        ])

        colA, colB = st.columns(2)
        with colA:
            st.plotly_chart(
                plotting.sky_polar_plotly(df, title=f"Sky track — {site.name}",
                                          horizon_profile=prof),
                alt=f"Sun and Earth sky track for {site.name}",
                width="stretch",
            )
        with colB:
            st.plotly_chart(
                plotting.elevation_vs_time_plotly(df, horizon_profile=prof,
                                                  title=f"Altitude vs time — {site.name}"),
                alt=f"Sun and Earth altitude over time for {site.name}",
                width="stretch",
            )

        with st.expander("Raw time series (first 200 rows)"):
            st.dataframe(df.head(200), alt=f"First 200 ephemeris rows for {site.name}")
            st.download_button(
                "⬇ Download full CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{site.site_id}_visibility.csv",
                mime="text/csv",
            )


# ---------------------------------------------------------------------------
# Mission simulation
# ---------------------------------------------------------------------------

st.markdown("### 🚀 Mission simulation")

st.markdown(
    "<div style='color:var(--text-muted); margin-bottom:.6rem'>"
    "Watch the full mission: launch from Earth, trans-lunar coast, lunar orbit, "
    "powered descent, then live surface operations at the chosen site."
    "</div>",
    unsafe_allow_html=True,
)

# Pick the focus site (default: first selected)
sim_site_id = st.selectbox(
    "Focus site for simulation",
    options=[s.site_id for s in selected_sites],
    format_func=lambda sid: next(s.name for s in selected_sites if s.site_id == sid),
    key="sim_site",
)

sim_site = next(s for s in selected_sites if s.site_id == sim_site_id)

# Launch date defaults to 3 days before the start_date so the simulation lands
# roughly at the start of the analysis window
launch_date = st.date_input(
    "Launch date (UTC)",
    value=(datetime.combine(start_date, datetime.min.time())
           - timedelta(days=3)).date(),
    key="sim_launch_date",
)

transit_days = st.slider(
    "Transit time (days)", 1, 7, 3,
    help="Days from launch to landing.",
    key="sim_transit",
)
sim_step = st.select_slider(
    "Surface resolution (min)",
    options=[5, 10, 15, 30, 60],
    value=15,
    key="sim_step",
)

# Build / reuse the mission plan
@st.cache_data(show_spinner=False)
def _build_plan_cached(site_row, launch_iso, transit_days, step_minutes):
    site_obj = sites.Site(*site_row)
    launch_dt = datetime.fromisoformat(launch_iso)
    if launch_dt.tzinfo is None:
        launch_dt = launch_dt.replace(tzinfo=timezone.utc)
    return sim.plan_mission(site_obj, launch_dt,
                            transit_days=float(transit_days),
                            surface_days=5.0,
                            step_minutes=float(step_minutes))

sim_site_row = (
    sim_site.site_id, sim_site.name, sim_site.lat_deg, sim_site.lon_deg,
    sim_site.elev_m, sim_site.description, sim_site.region,
)
plan = _build_plan_cached(
    sim_site_row,
    launch_date.isoformat(), int(transit_days), int(sim_step),
)

# Pre-render the frame sequence
if "sim_frames" not in st.session_state or st.session_state.get("sim_plan_id") != sim_site.site_id + "|" + launch_date.isoformat() + "|" + str(transit_days) + "|" + str(sim_step):
    with st.spinner("Rendering mission frames…"):
        st.session_state.sim_frames = sim.build_frame_sequence(plan, n_frames=240)
        st.session_state.sim_plan_id = sim_site.site_id + "|" + launch_date.isoformat() + "|" + str(transit_days) + "|" + str(sim_step)

frames = st.session_state.sim_frames
n_frames = len(frames)
frame_seconds = [t for (t, _) in frames]

# Controls
ctrl_cols = st.columns([1, 1, 2, 1])
with ctrl_cols[0]:
    play = st.button("▶ Play", width="stretch", disabled=not sim.MATPLOTLIB_AVAILABLE)
with ctrl_cols[1]:
    pause = st.button("⏸ Pause", width="stretch", disabled=not sim.MATPLOTLIB_AVAILABLE)
with ctrl_cols[2]:
    if n_frames > 1:
        frame_idx = st.slider(
            "Mission time",
            min_value=0, max_value=n_frames - 1,
            value=st.session_state.get("sim_frame_idx", 0),
            step=1,
            label_visibility="visible",
            key="sim_frame_slider",
        )
    else:
        frame_idx = 0
        st.caption("Frame animation is unavailable; the complete surface window is shown below.")
    st.session_state.sim_frame_idx = frame_idx
with ctrl_cols[3]:
    speed = st.select_slider(
        "Speed",
        options=[0.5, 1.0, 2.0, 4.0, 8.0],
        value=1.0,
        key="sim_speed",
        disabled=not sim.MATPLOTLIB_AVAILABLE,
    )

# Auto-play loop
if "sim_last_tick" not in st.session_state:
    st.session_state.sim_last_tick = 0.0
if play:
    import time as _t
    now = _t.time()
    dt = now - st.session_state.sim_last_tick
    st.session_state.sim_last_tick = now
    advance = max(1, int(speed * dt * 6))  # ~6 fps live loop
    new_idx = (frame_idx + advance) % n_frames
    st.session_state.sim_frame_idx = new_idx
    st.session_state.sim_frame_slider = new_idx
    _t.sleep(1.0 / 8.0)
    st.rerun()
if pause:
    st.session_state.sim_last_tick = 0.0

# Render the chosen frame
_, fig = frames[frame_idx]
frame_placeholder = st.empty()
if sim.MATPLOTLIB_AVAILABLE:
    frame_placeholder.pyplot(fig, width="stretch", alt="Illustrative mission simulator frame")
    sim.plt.close(fig)

    # Live HUD under the animated frame.
    t_sec = frame_seconds[frame_idx]
    phase = plan.phase_at(t_sec)
    surf_t = (t_sec - plan.launch_seconds - plan.transit_seconds
              - plan.orbit_seconds - plan.descent_seconds)
    if phase == sim.MissionPhase.SURFACE_OPS and len(plan.surface_sun_alt):
        idx = int(np.clip(surf_t / plan.surface_seconds *
                          (len(plan.surface_sun_alt) - 1), 0,
                          (len(plan.surface_sun_alt) - 1)))
        sa = float(plan.surface_sun_alt[idx])
        ha = float(plan.horizon_at[idx])
        ea = float(plan.surface_earth_alt[idx])
        sun_on = sa > ha
        earth_on = ea > ha
        power_pct = max(0.0, sa / 90.0) * 100 if sun_on else 0.0
        comm_pct = max(0.0, min(1.0, (ea - ha) / 30.0)) * 100 if earth_on else 0.0
    else:
        sa = ea = ha = power_pct = comm_pct = 0.0
        sun_on = earth_on = False

    render_kpi_row([
        ("Mission phase", phase.value, ""),
        ("Sun altitude", f"{sa:+.2f}°", "sun"),
        ("Earth altitude", f"{ea:+.2f}°", "earth"),
        ("Solar power", f"{power_pct:.0f}%  ({'ON' if sun_on else 'OFF'})", "sun"),
        ("Earth comm", f"{comm_pct:.0f}%  ({'ON' if earth_on else 'OFF'})", "earth"),
    ])
else:
    st.info("Matplotlib animation is unavailable in this runtime. The computed surface-operations window is shown below.")
    st.plotly_chart(
        plotting.mission_surface_timeline(
            plan.surface_times, plan.surface_sun_alt, plan.surface_earth_alt,
            plan.horizon_at, title=f"Surface operations — {sim_site.name}",
        ),
        alt=f"Sun and Earth altitude during surface operations at {sim_site.name}",
        width="stretch",
    )
    sun_visible = np.asarray(plan.surface_sun_alt) > np.asarray(plan.horizon_at)
    earth_visible = np.asarray(plan.surface_earth_alt) > np.asarray(plan.horizon_at)
    render_kpi_row([
        ("Mission phase", "SURFACE OPS", ""),
        ("Sun above profile", f"{sun_visible.mean() * 100.0:.1f}%", "sun"),
        ("Earth above profile", f"{earth_visible.mean() * 100.0:.1f}%", "earth"),
        ("Horizon source", plan.profile.source, ""),
    ])


# ---------------------------------------------------------------------------
# Cross-site comparison
# ---------------------------------------------------------------------------

st.markdown("### 🌌 Cross-site comparison")

st.markdown(
    "<div style='color:var(--text-muted); margin-bottom:.6rem'>"
    "Side-by-side sky tracks across all selected sites for the chosen window."
    "</div>",
    unsafe_allow_html=True,
)

comparison_inputs = {v["site"].name: (v["df"], v["profile"]) for v in results.values()}
if sim.MATPLOTLIB_AVAILABLE:
    fig = plotting.comparison_grid_mpl(comparison_inputs, title="Sky tracks for selected sites")
    st.pyplot(fig, width="stretch", alt="Cross-site Sun and Earth sky-track comparison")
else:
    st.plotly_chart(
        plotting.comparison_grid_plotly(comparison_inputs, title="Sky tracks for selected sites"),
        alt="Cross-site Sun and Earth altitude tracks",
        width="stretch",
    )


# ---------------------------------------------------------------------------
# Date sweep
# ---------------------------------------------------------------------------

st.markdown("### 📅 Seasonal variation")

c1, c2 = st.columns([1, 2])
with c1:
    sweep_metric = st.selectbox(
        "Metric",
        options=[
            "sun_above_real_horizon_pct",
            "sun_max_altitude_deg",
            "sunlit_continuous_hours_max",
            "earth_above_real_horizon_pct",
            "earth_min_altitude_deg",
            "earth_blackout_minutes",
        ],
        index=0,
    )
with c2:
    n_dates = st.slider("Dates to sweep", 4, 24, 12, step=2)

metric_labels = {
    "sun_above_real_horizon_pct":  "% time above selected horizon profile",
    "sun_max_altitude_deg":        "Maximum sun altitude (°)",
    "sunlit_continuous_hours_max": "Longest continuous sunlit streak (h)",
    "earth_above_real_horizon_pct":"% time Earth is above selected horizon profile",
    "earth_min_altitude_deg":      "Minimum Earth altitude (°)",
    "earth_blackout_minutes":      "Longest Earth blackout (min)",
}

with st.spinner("Sweeping dates…"):
    sweeps = {}
    base = start_dt
    for v in results.values():
        site = v["site"]
        sd = _date_sweep_cached(
            (site.site_id, site.name, site.lat_deg, site.lon_deg,
             site.elev_m, site.description, site.region),
            base.isoformat(),
            int(n_dates),
        )
        sweeps[v["site"].name] = sd

    st.plotly_chart(
        plotting.date_sweep_heatmap_plotly(
            sweeps, sweep_metric,
            title=f"{metric_labels[sweep_metric]} — variation across the year",
        ),
        alt="Seasonal variation in lunar surface sunlight and Earth visibility",
        width="stretch",
    )
st.caption("Seasonal summaries use the cached six-hour JPL Horizons dataset when available and apply only a processed DEM. Synthetic profiles are not used as scientific visibility masks.")


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(
    "<div style='color:var(--text-muted); font-size:.85rem; text-align:center'>"
    "Ephemerides use NAIF SPICE when usable, otherwise NASA/JPL Horizons. "
    "Synthetic horizon profiles are illustrative, not LOLA terrain. Research/education prototype; not flight-certified software."
    "</div>",
    unsafe_allow_html=True,
)
