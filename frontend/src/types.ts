export interface Site {
  site_id: string;
  name: string;
  lat_deg: number;
  lon_deg: number;
  elev_m: number;
  description: string;
  region: string;
  coordinate_note: string;
  available_profile_source?: string;
}

export interface TerrainRegion {
  tile_id: string;
  region_name: string;
  center_latitude_deg: number;
  center_longitude_deg_east: number;
  center_elevation_m: number;
  resolution_m: number;
  bounds_m: Record<string, number>;
  coordinate_basis: string;
  source_url: string;
  recommended_horizon_radius_km: number;
}

export interface Summary {
  site_id: string;
  site_name: string;
  start_utc: string;
  end_utc: string;
  duration_hours: number;
  backend: string;
  sun_above_horizon_pct: number;
  sun_above_real_horizon_pct: number;
  sun_mean_altitude_deg: number;
  sun_max_altitude_deg: number;
  earth_above_horizon_pct: number;
  earth_above_real_horizon_pct: number;
  earth_mean_altitude_deg: number;
  earth_min_altitude_deg: number;
  earth_max_altitude_deg: number;
  sunlit_continuous_hours_max: number;
  earth_blackout_minutes: number;
}

export interface EphemerisSample {
  time_utc: string;
  sun_alt_deg: number;
  sun_az_deg: number;
  earth_alt_deg: number;
  earth_az_deg: number;
  sun_horizon_deg?: number;
  earth_horizon_deg?: number;
  sun_visible: boolean;
  earth_visible: boolean;
}

export interface HorizonProfile {
  source: string;
  site_lat_deg: number;
  site_lon_deg: number;
  site_elev_m: number;
  azimuth_deg: number[];
  elevation_deg: number[];
  is_measured_dem: boolean;
  coverage_range_km?: number | null;
  source_detail?: string | null;
  source_url?: string | null;
  resolution_m?: number | null;
}

export interface GoldenWindow {
  start_utc: string;
  end_utc: string;
  duration_hours: number;
  sample_count: number;
}

export interface AnalysisResult {
  site: Site;
  summary: Summary;
  time_series: EphemerisSample[];
  horizon_profile: HorizonProfile | null;
  golden_windows: GoldenWindow[];
  simultaneous_visible_pct: number;
  provenance: {
    ephemeris_backend: string;
    source_type: string;
    horizon_source: string;
    display_horizon_source: string | null;
    terrain_note: string;
    coordinate_note: string;
    sampling_note: string;
  };
}

export interface ScienceStatus {
  spice_available: boolean;
  ephemeris_backend: string;
  ephemeris_note: string;
  configured_horizon_profiles: Record<string, string>;
  measured_dem_available: boolean;
  ml_model_available: boolean;
  ml_model_error: string | null;
  dataset_provenance: Record<string, unknown> | null;
  terrain_provenance?: Record<string, unknown> | null;
  limitations: string[];
}

export interface ModelMetrics {
  trained_at_utc: string;
  model: string;
  dataset_source: string;
  dataset_rows: number;
  site_count: number;
  date_coverage_utc: string[];
  altitude_metrics: Record<string, Record<string, number>>;
  azimuth_metrics: Record<string, number>;
  interpretation: string;
}

export interface SeasonalSample {
  date_utc: string;
  sun_above_real_horizon_pct: number;
  sun_max_altitude_deg: number;
  sunlit_continuous_hours_max: number;
  earth_above_real_horizon_pct: number;
  earth_min_altitude_deg: number;
  earth_blackout_minutes: number;
}

export interface SeasonalSite {
  site: Site;
  horizon_source: string;
  display_horizon_source: string;
  samples: SeasonalSample[];
}

export interface SeasonalResult {
  sites: SeasonalSite[];
  stride_days: number;
  provenance: {
    source: string;
    terrain_note: string;
    sampling_note: string;
  };
}

export interface ScenarioComparison {
  scenario_a: AnalysisResult;
  scenario_b: AnalysisResult;
  scenario_b_minus_a: Record<string, number>;
}

export interface MissionPhase {
  name: string;
  start_seconds: number;
  end_seconds: number;
  illustrative: boolean;
}

export interface SurfaceTelemetry extends EphemerisSample {
  mission_seconds: number;
  phase: string;
}

export interface MissionPlan {
  site: Site;
  launch_utc: string;
  landing_utc: string;
  duration_seconds: number;
  phases: MissionPhase[];
  surface_telemetry: SurfaceTelemetry[];
  horizon_profile: HorizonProfile;
  provenance: {
    ephemeris_backend: string;
    surface_data: string;
    illustration_note: string;
    horizon_note: string;
  };
  simulator_html: string;
}

export interface SavedMissionProfile {
  id: string;
  name: string;
  site_id: string;
  site_name: string;
  launch_utc: string;
  transit_days: number;
  surface_days: number;
  step_minutes: number;
  created_at: string;
}

export interface PhysicalRecommendation {
  ml_candidate: Record<string, unknown>;
  summary: Summary;
  physical_score: number;
  simultaneous_visible_pct: number;
  horizon_source: string;
  terrain_note: string;
}

export interface RecommendationResult {
  ml_candidates: Record<string, unknown>[];
  excluded_sites: string[];
  physical_checks: PhysicalRecommendation[];
  recommended: PhysicalRecommendation | null;
  score_definition: string;
  metrics: ModelMetrics | null;
  limitations: string[];
}
