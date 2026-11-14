import type {
  AnalysisResult,
  MissionPlan,
  ModelMetrics,
  RecommendationResult,
  SavedMissionProfile,
  ScenarioComparison,
  ScienceStatus,
  SeasonalResult,
  Site,
  TerrainRegion,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Network error";
    throw new ApiError(`Backend is unavailable. Check the FastAPI service and try again. (${message})`);
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (payload.detail) detail = JSON.stringify(payload.detail);
    } catch {
      // Preserve the HTTP status message when the backend did not return JSON.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

const post = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: "POST",
  body: JSON.stringify(body),
  signal,
});

export interface ScenarioInput {
  site_id: string;
  start_utc: string;
  duration_hours: number;
  step_minutes: number;
  include_terrain: boolean;
  site_name?: string;
  lat_deg?: number;
  lon_deg?: number;
  elev_m?: number;
}

export async function getHealth(signal?: AbortSignal) {
  return request<{ status: string; ephemeris_backend: string; ephemeris_note: string }>("/api/health", { signal });
}

export async function getSites(signal?: AbortSignal) {
  return request<Site[]>("/api/sites", { signal });
}

export async function getTerrainRegions(signal?: AbortSignal) {
  return request<TerrainRegion[]>("/api/terrain/regions", { signal });
}

export async function getScienceStatus(signal?: AbortSignal) {
  return request<ScienceStatus>("/api/science/status", { signal });
}

export async function getModelMetrics(signal?: AbortSignal) {
  return request<{ available: boolean; error: string | null; metrics: ModelMetrics | null }>("/api/ml/metrics", { signal });
}

export async function analyzeSite(input: ScenarioInput, signal?: AbortSignal) {
  return request<AnalysisResult>("/api/analyze", post(input, signal));
}

export async function compareScenarios(scenarioA: ScenarioInput, scenarioB: ScenarioInput, signal?: AbortSignal) {
  return request<ScenarioComparison>("/api/compare", post({ scenario_a: scenarioA, scenario_b: scenarioB }, signal));
}

export async function getSeasonalSweep(input: {
  site_ids: string[];
  start_utc: string;
  n_dates: number;
  duration_hours: number;
  step_minutes: number;
  include_terrain: boolean;
}, signal?: AbortSignal) {
  return request<SeasonalResult>("/api/seasonal-sweep", post(input, signal));
}

export async function getMissionPlan(input: {
  site_id: string;
  launch_utc: string;
  transit_days: number;
  surface_days: number;
  step_minutes: number;
}, signal?: AbortSignal) {
  return request<MissionPlan>("/api/simulation/plan", post(input, signal));
}

export async function getSavedMissionProfiles(ownerId: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ owner_id: ownerId });
  return request<SavedMissionProfile[]>(`/api/saved-missions?${query}`, { signal });
}

export async function getSavedMissionStoreStatus(signal?: AbortSignal) {
  return request<{ configured: boolean }>("/api/saved-missions/status", { signal });
}

export async function saveMissionProfile(input: {
  owner_id: string;
  name: string;
  site_id: string;
  site_name: string;
  launch_utc: string;
  transit_days: number;
  surface_days: number;
  step_minutes: number;
}) {
  return request<SavedMissionProfile>("/api/saved-missions", post(input));
}

export async function deleteMissionProfile(profileId: string, ownerId: string) {
  const query = new URLSearchParams({ owner_id: ownerId });
  return request<void>(`/api/saved-missions/${encodeURIComponent(profileId)}?${query}`, { method: "DELETE" });
}

export async function getRecommendation(input: {
  site_ids: string[];
  start_utc: string;
  duration_hours: number;
  sample_hours: number;
  step_minutes: number;
  include_terrain: boolean;
}, signal?: AbortSignal) {
  return request<RecommendationResult>("/api/recommend", post(input, signal));
}
