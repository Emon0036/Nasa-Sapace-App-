import { useEffect, useRef, useState } from "react";
import { Activity, BookmarkPlus, Database, FolderOpen, Play, Trash2 } from "lucide-react";
import { deleteMissionProfile, getMissionPlan, getSavedMissionProfiles, getSavedMissionStoreStatus, saveMissionProfile } from "../services/api";
import type { MissionPhase, MissionPlan, SavedMissionProfile, Site, SurfaceTelemetry } from "../types";
import { MissionExperience } from "../components/MissionExperience";
import type { MissionCameraMode } from "../components/MissionScene3D";
import { EmptyState, SectionTitle } from "../components/common";

interface MissionSimulatorProps {
  sites: Site[];
  selectedSiteIds: string[];
  startUtc: string;
  defaultStep: number;
}

function addLocalHours(utc: string, offsetHours: number) {
  const date = new Date(new Date(utc).getTime() + offsetHours * 60 * 60 * 1000);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function localToUtc(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("Choose a valid launch time.");
  return date.toISOString();
}

function utcToLocalInput(value: string) {
  const date = new Date(value);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function browserOwnerId() {
  const key = "lunar-horizon-saved-missions-owner-v1";
  try {
    const saved = window.localStorage.getItem(key);
    if (saved) return saved;
    const created = window.crypto.randomUUID();
    window.localStorage.setItem(key, created);
    return created;
  } catch {
    return window.crypto.randomUUID();
  }
}

function phaseAt(plan: MissionPlan, seconds: number): MissionPhase {
  const lastIndex = plan.phases.length - 1;
  return plan.phases.find((phase, index) => seconds >= phase.start_seconds && (seconds < phase.end_seconds || index === lastIndex)) ?? plan.phases[lastIndex];
}

function surfaceSampleAt(plan: MissionPlan, seconds: number): { sample?: SurfaceTelemetry; projected: boolean } {
  const samples = plan.surface_telemetry;
  const surfacePhase = plan.phases.find((phase) => phase.name === "SURFACE OPS");
  if (!surfacePhase || !samples.length) return { projected: false };
  const projected = seconds < surfacePhase.start_seconds;
  if (projected) return { sample: samples[0], projected: true };
  const span = Math.max(1, surfacePhase.end_seconds - surfacePhase.start_seconds);
  const ratio = Math.max(0, Math.min(1, (seconds - surfacePhase.start_seconds) / span));
  const index = Math.min(samples.length - 1, Math.round(ratio * (samples.length - 1)));
  return { sample: samples[index], projected: false };
}

export function MissionSimulator({ sites, selectedSiteIds, startUtc, defaultStep }: MissionSimulatorProps) {
  const selected = sites.filter((site) => selectedSiteIds.includes(site.site_id));
  const defaultSite = selected[0]?.site_id ?? sites[0]?.site_id ?? "";
  const [siteId, setSiteId] = useState(defaultSite);
  const [launchLocal, setLaunchLocal] = useState(addLocalHours(startUtc, -72));
  const [transitDays, setTransitDays] = useState(3);
  const [surfaceDays, setSurfaceDays] = useState(5);
  const [stepMinutes, setStepMinutes] = useState(Math.max(5, defaultStep));
  const [plan, setPlan] = useState<MissionPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSetup, setShowSetup] = useState(true);
  const [seconds, setSeconds] = useState(0);
  const secondsRef = useRef(0);
  const [playing, setPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(3600);
  const [cameraMode, setCameraMode] = useState<MissionCameraMode | "sky-radar">("overview");
  const [ownerId] = useState(browserOwnerId);
  const [savedProfiles, setSavedProfiles] = useState<SavedMissionProfile[]>([]);
  const [storeConfigured, setStoreConfigured] = useState(false);
  const [selectedSavedProfile, setSelectedSavedProfile] = useState("");
  const [storageError, setStorageError] = useState("");
  const [storageMessage, setStorageMessage] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [removingProfile, setRemovingProfile] = useState(false);

  const setMissionTime = (value: number, pause = true) => {
    const duration = plan?.duration_seconds ?? 0;
    const next = Math.max(0, Math.min(duration, value));
    secondsRef.current = next;
    setSeconds(next);
    if (pause) setPlaying(false);
  };

  useEffect(() => {
    if (!siteId || !sites.some((site) => site.site_id === siteId)) setSiteId(defaultSite);
  }, [defaultSite, siteId, sites]);
  useEffect(() => setLaunchLocal(addLocalHours(startUtc, -72)), [startUtc]);

  useEffect(() => {
    const controller = new AbortController();
    void getSavedMissionStoreStatus(controller.signal).then(async ({ configured }) => {
      if (controller.signal.aborted) return;
      if (!configured) {
        setStoreConfigured(false);
        setStorageError("Set DATABASE_URL on the API service to enable cloud saves.");
        return;
      }
      setStoreConfigured(true);
      const profiles = await getSavedMissionProfiles(ownerId, controller.signal);
      if (controller.signal.aborted) return;
      setSavedProfiles(profiles);
      setStorageError("");
    }).catch((caught: unknown) => {
      if (controller.signal.aborted) return;
      setStoreConfigured(false);
      setStorageError(caught instanceof Error ? caught.message : "Cloud mission storage is unavailable.");
    });
    return () => controller.abort();
  }, [ownerId]);

  useEffect(() => {
    if (!plan) return;
    secondsRef.current = 0;
    setSeconds(0);
    setPlaying(false);
  }, [plan]);

  useEffect(() => {
    if (!plan || !playing) return undefined;
    let frame = 0;
    let previousFrame = performance.now();
    let previousUiUpdate = previousFrame;
    const advance = (now: number) => {
      const delta = Math.max(0, Math.min(.1, (now - previousFrame) / 1000));
      previousFrame = now;
      const next = Math.min(plan.duration_seconds, secondsRef.current + delta * playbackRate);
      secondsRef.current = next;
      if (now - previousUiUpdate >= 40 || next >= plan.duration_seconds) {
        setSeconds(next);
        previousUiUpdate = now;
      }
      if (next >= plan.duration_seconds) {
        setPlaying(false);
        return;
      }
      frame = window.requestAnimationFrame(advance);
    };
    frame = window.requestAnimationFrame(advance);
    return () => window.cancelAnimationFrame(frame);
  }, [plan, playing, playbackRate]);

  const buildPlan = async () => {
    setLoading(true);
    setError("");
    try {
      const nextPlan = await getMissionPlan({
        site_id: siteId,
        launch_utc: localToUtc(launchLocal),
        transit_days: transitDays,
        surface_days: surfaceDays,
        step_minutes: stepMinutes,
      });
      setPlan(nextPlan);
      secondsRef.current = 0;
      setSeconds(0);
      setPlaying(false);
      setShowSetup(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not calculate mission telemetry.");
    } finally {
      setLoading(false);
    }
  };

  const saveCurrentProfile = async () => {
    if (!plan) return;
    setSavingProfile(true);
    setStorageError("");
    setStorageMessage("");
    try {
      const profile = await saveMissionProfile({
        owner_id: ownerId,
        name: `${plan.site.name} · ${new Date(plan.launch_utc).toISOString().slice(0, 10)}`,
        site_id: plan.site.site_id,
        site_name: plan.site.name,
        launch_utc: plan.launch_utc,
        transit_days: transitDays,
        surface_days: surfaceDays,
        step_minutes: stepMinutes,
      });
      setSavedProfiles((current) => [profile, ...current].slice(0, 50));
      setSelectedSavedProfile(profile.id);
      setStorageMessage("Mission profile saved to the SQL library.");
    } catch (caught) {
      setStorageError(caught instanceof Error ? caught.message : "Cloud mission storage is unavailable.");
    } finally {
      setSavingProfile(false);
    }
  };

  const loadSavedProfile = () => {
    const profile = savedProfiles.find((item) => item.id === selectedSavedProfile);
    if (!profile) return;
    setSiteId(profile.site_id);
    setLaunchLocal(utcToLocalInput(profile.launch_utc));
    setTransitDays(profile.transit_days);
    setSurfaceDays(profile.surface_days);
    setStepMinutes(profile.step_minutes);
    setShowSetup(true);
    setStorageMessage(`Loaded ${profile.name}. Build the simulation to refresh its science telemetry.`);
  };

  const removeSavedProfile = async () => {
    if (!selectedSavedProfile) return;
    setRemovingProfile(true);
    setStorageError("");
    setStorageMessage("");
    try {
      await deleteMissionProfile(selectedSavedProfile, ownerId);
      setSavedProfiles((current) => current.filter((item) => item.id !== selectedSavedProfile));
      setSelectedSavedProfile("");
      setStorageMessage("Saved profile removed.");
    } catch (caught) {
      setStorageError(caught instanceof Error ? caught.message : "Could not remove the saved mission profile.");
    } finally {
      setRemovingProfile(false);
    }
  };

  const activePhase = plan ? phaseAt(plan, seconds) : undefined;
  const surfaceState = plan ? surfaceSampleAt(plan, seconds) : { projected: false };
  const phaseIndex = plan && activePhase ? plan.phases.findIndex((phase) => phase.name === activePhase.name) : -1;
  const previousPhase = () => {
    if (!plan || phaseIndex <= 0) return;
    setMissionTime(plan.phases[phaseIndex - 1].start_seconds);
  };
  const nextPhase = () => {
    if (!plan || phaseIndex < 0 || phaseIndex >= plan.phases.length - 1) return;
    setMissionTime(plan.phases[phaseIndex + 1].start_seconds);
  };
  const togglePlayback = () => {
    if (!plan) return;
    if (!playing && seconds >= plan.duration_seconds) setMissionTime(0, false);
    setPlaying((value) => !value);
  };

  return <div className="mission-simulator-page">
    <div className={`simulator-page-heading ${plan ? "simulator-heading-loaded" : ""}`}>
      <div>
        <div className="eyebrow">SOUTH POLE OPERATIONS · LIVE SIMULATION</div>
        <h1>Mission Simulation</h1>
        <p>Follow the mission phases and scrub time. Surface Sun/Earth telemetry is calculated; the flight path is illustrative.</p>
      </div>
      <div className={`simulator-live-state ${plan ? "simulator-live" : ""}`}>
        <Activity size={17} aria-hidden="true" />
        <span><strong>{plan ? "Telemetry ready" : "Simulation setup"}</strong><small>{plan ? "Surface data connected" : "Choose a site and start time"}</small></span>
      </div>
    </div>
    <section className="panel simulator-setup-panel">
      {plan && !showSetup ? <div className="simulator-profile-summary">
        <div><span>MISSION PROFILE</span><strong>{plan.site.name}</strong><small>{launchLocal.replace("T", " ")} local · {transitDays}-day transit · {surfaceDays}-day surface · {stepMinutes}-minute cadence</small></div>
        <button className="button button-secondary" onClick={() => setShowSetup(true)}>Edit mission setup</button>
      </div> : <>
        <SectionTitle eyebrow="MISSION PROFILE" title="Set the mission parameters" />
        <div className="inline-controls simulator-form">
          <label className="control-field"><span>Landing site</span><select value={siteId} onChange={(event) => setSiteId(event.target.value)}>{sites.map((site) => <option key={site.site_id} value={site.site_id}>{site.name}</option>)}</select></label>
          <label className="control-field"><span>Launch date &amp; time · local</span><input type="datetime-local" value={launchLocal} onChange={(event) => setLaunchLocal(event.target.value)} /></label>
          <label className="control-field"><span>Transit duration</span><select value={transitDays} onChange={(event) => setTransitDays(Number(event.target.value))}>{[1, 2, 3, 4, 5, 6, 7].map((day) => <option key={day} value={day}>{day} days</option>)}</select></label>
          <label className="control-field"><span>Surface duration</span><select value={surfaceDays} onChange={(event) => setSurfaceDays(Number(event.target.value))}>{[1, 3, 5, 7, 10].map((day) => <option key={day} value={day}>{day} days</option>)}</select></label>
          <label className="control-field"><span>Surface data interval</span><select value={stepMinutes} onChange={(event) => setStepMinutes(Number(event.target.value))}>{[5, 10, 15, 30, 60].map((step) => <option key={step} value={step}>{step} min</option>)}</select></label>
          <button className="button button-primary simulator-build-button" onClick={() => void buildPlan()} disabled={loading || !siteId}>{loading ? <span className="spinner" /> : <Play size={17} />}{loading ? "Building…" : plan ? "Update simulation" : "Build simulation"}</button>
        </div>
        <div className="simulator-setup-hint">Times are sent to the science API in UTC. Surface telemetry uses the selected ephemeris and terrain profile.</div>
      </>}
      <div className="mission-saved-profile-bar">
        <div className="mission-saved-profile-title"><Database size={16} /><span>Saved mission profiles</span><small>{savedProfiles.length}/50</small></div>
        <div className="mission-saved-profile-actions">
          <select aria-label="Saved mission profiles" value={selectedSavedProfile} onChange={(event) => setSelectedSavedProfile(event.target.value)}>
            <option value="">Choose a saved profile…</option>
            {savedProfiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}
          </select>
          <button className="button button-secondary button-small" onClick={loadSavedProfile} disabled={!selectedSavedProfile}><FolderOpen size={14} />Load</button>
          <button className="button button-secondary button-small" onClick={() => void removeSavedProfile()} disabled={!selectedSavedProfile || removingProfile} aria-label="Remove selected saved mission profile"><Trash2 size={14} />Remove</button>
          <button className="button button-secondary button-small" onClick={() => void saveCurrentProfile()} disabled={!plan || !storeConfigured || savingProfile}><BookmarkPlus size={14} />{savingProfile ? "Saving…" : "Save current mission"}</button>
        </div>
        {storageError ? <small className="mission-saved-profile-status mission-storage-error">Cloud SQL library unavailable: {storageError}</small> : storageMessage ? <small className="mission-saved-profile-status">{storageMessage}</small> : <small className="mission-saved-profile-status">Saved plans keep mission inputs only; telemetry is recalculated when you build.</small>}
      </div>
      {error && <div className="notice notice-error">{error}</div>}
    </section>
    {plan && activePhase ? <MissionExperience
      plan={plan}
      seconds={seconds}
      phase={activePhase}
      telemetry={surfaceState.sample}
      projected={surfaceState.projected}
      cameraMode={cameraMode}
      onCameraModeChange={setCameraMode}
      playing={playing}
      playbackRate={playbackRate}
      onTogglePlayback={togglePlayback}
      onReset={() => setMissionTime(0)}
      onPreviousPhase={previousPhase}
      onNextPhase={nextPhase}
      onSeek={(value) => setMissionTime(value)}
      onPlaybackRateChange={setPlaybackRate}
    /> : <EmptyState title="Build your mission simulation" detail="Choose a landing site and launch time. The simulator will load the mission timeline and calculate surface Sun and Earth positions." action={<div className="empty-state-science-note">Flight phase artwork is illustrative; surface sky telemetry comes from the science engine.</div>} />}
  </div>;
}
