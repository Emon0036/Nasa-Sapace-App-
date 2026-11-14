import { useState } from "react";
import { ChevronDown, ChevronUp, Crosshair, Play, Plus, SlidersHorizontal } from "lucide-react";
import type { Site, TerrainRegion } from "../types";

export interface CustomSiteInput {
  site_id: string;
  site_name: string;
  lat_deg: number;
  lon_deg: number;
  elev_m: number;
}

interface MissionControlsProps {
  sites: Site[];
  terrainRegions: TerrainRegion[];
  selectedSiteIds: string[];
  onSelectedSitesChange: (ids: string[]) => void;
  startLocal: string;
  onStartLocalChange: (value: string) => void;
  durationDays: number;
  onDurationDaysChange: (value: number) => void;
  stepMinutes: number;
  onStepMinutesChange: (value: number) => void;
  includeTerrain: boolean;
  onIncludeTerrainChange: (value: boolean) => void;
  loading: boolean;
  onRun: (custom: CustomSiteInput | null) => void;
}

export function MissionControls(props: MissionControlsProps) {
  const [expanded, setExpanded] = useState(false);
  const [customEnabled, setCustomEnabled] = useState(false);
  const [customName, setCustomName] = useState("Custom lunar site");
  const [customLat, setCustomLat] = useState("-89.5");
  const [customLon, setCustomLon] = useState("0");
  const [customElevation, setCustomElevation] = useState("0");
  const [selectedTerrainRegionId, setSelectedTerrainRegionId] = useState("");
  const [validation, setValidation] = useState("");

  const applyTerrainRegion = (tileId: string) => {
    setSelectedTerrainRegionId(tileId);
    const region = props.terrainRegions.find((item) => item.tile_id === tileId);
    if (!region) return;
    setCustomEnabled(true);
    props.onIncludeTerrainChange(true);
    setCustomName(`LOLA ${region.tile_id} · ${region.region_name} sample`);
    setCustomLat(region.center_latitude_deg.toFixed(6));
    setCustomLon(region.center_longitude_deg_east.toFixed(6));
    setCustomElevation(region.center_elevation_m.toFixed(1));
  };

  const toggleSite = (siteId: string) => {
    const next = props.selectedSiteIds.includes(siteId)
      ? props.selectedSiteIds.filter((id) => id !== siteId)
      : [...props.selectedSiteIds, siteId];
    props.onSelectedSitesChange(next);
  };

  const run = () => {
    setValidation("");
    if (!props.selectedSiteIds.length && !customEnabled) {
      setValidation("Select at least one site or add custom coordinates.");
      return;
    }
    const custom: CustomSiteInput | null = customEnabled ? {
      site_id: "custom_site",
      site_name: customName.trim() || "Custom lunar site",
      lat_deg: Number(customLat),
      lon_deg: Number(customLon),
      elev_m: Number(customElevation),
    } : null;
    if (custom && (!Number.isFinite(custom.lat_deg) || custom.lat_deg < -90 || custom.lat_deg > 90
      || !Number.isFinite(custom.lon_deg) || custom.lon_deg < -180 || custom.lon_deg > 360
      || !Number.isFinite(custom.elev_m) || custom.elev_m < -12000 || custom.elev_m > 12000)) {
      setValidation("Custom coordinates must be within latitude −90..90°, east longitude −180..360°, and elevation −12,000..12,000 m.");
      return;
    }
    if (!props.startLocal || Number.isNaN(new Date(props.startLocal).getTime())) {
      setValidation("Choose a valid mission start date and time.");
      return;
    }
    props.onRun(custom);
  };

  return <section className="mission-controls panel">
    <div className="mission-controls-heading"><div><div className="eyebrow"><SlidersHorizontal size={12} /> ANALYSIS INPUTS</div><h2>Mission parameters</h2></div><button className="subtle-button" onClick={() => setExpanded((open) => !open)} aria-expanded={expanded}>{expanded ? "Hide sites" : "Select sites"}{expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}</button></div>
    {expanded && <div className="site-selection-grid">
      {props.sites.map((site) => <label className={`site-option ${props.selectedSiteIds.includes(site.site_id) ? "site-option-selected" : ""}`} key={site.site_id}><input type="checkbox" checked={props.selectedSiteIds.includes(site.site_id)} onChange={() => toggleSite(site.site_id)} /><span className="site-check" /><span><strong>{site.name}</strong><small>{site.lat_deg.toFixed(2)}° / {site.lon_deg.toFixed(2)}° E · {site.region.replace("_", " ")}</small></span></label>)}
      <label className={`site-option custom-site-toggle ${customEnabled ? "site-option-selected" : ""}`}><input type="checkbox" checked={customEnabled} onChange={(event) => setCustomEnabled(event.target.checked)} /><span className="site-check" /><span><strong>Add custom coordinates</strong><small>Latitude, east longitude, elevation</small></span><Plus size={15} /></label>
    </div>}
    <div className="mission-control-grid">
      <label className="control-field control-date"><span>Mission start · device local time</span><input type="datetime-local" value={props.startLocal} onChange={(event) => props.onStartLocalChange(event.target.value)} /></label>
      <label className="control-field"><span>Observation window</span><select value={props.durationDays} onChange={(event) => props.onDurationDaysChange(Number(event.target.value))}>{[1, 3, 5, 7, 10].map((days) => <option key={days} value={days}>{days} day{days > 1 ? "s" : ""}</option>)}</select></label>
      <label className="control-field"><span>Sampling cadence</span><select value={props.stepMinutes} onChange={(event) => props.onStepMinutesChange(Number(event.target.value))}>{[5, 10, 15, 30, 60].map((step) => <option key={step} value={step}>{step} min</option>)}</select></label>
      <label className="terrain-toggle"><input type="checkbox" checked={props.includeTerrain} onChange={(event) => props.onIncludeTerrainChange(event.target.checked)} /><span className="toggle-track" /><span><strong>Use LOLA terrain where covered</strong><small>Other locations use geometric visibility</small></span></label>
      <button className="button button-primary run-button" onClick={run} disabled={props.loading}>{props.loading ? <span className="spinner" /> : <Play size={15} fill="currentColor" />}{props.loading ? "Calculating visibility…" : "Compute visibility"}</button>
    </div>
    {customEnabled && <div className="custom-site-fields">
      <div className="custom-fields-title"><Crosshair size={14} /><span>Custom observer coordinates · not survey verified</span></div>
      {props.terrainRegions.length > 0 && <label className="control-field terrain-region-preset"><span>LOLA terrain region</span><select value={selectedTerrainRegionId} onChange={(event) => applyTerrainRegion(event.target.value)}><option value="">Enter coordinates manually</option>{props.terrainRegions.map((region) => <option key={region.tile_id} value={region.tile_id}>{region.tile_id} · {region.region_name} (tile center)</option>)}</select></label>}
      <label className="control-field"><span>Site label</span><input value={customName} onChange={(event) => { setSelectedTerrainRegionId(""); setCustomName(event.target.value); }} maxLength={120} /></label>
      <label className="control-field"><span>Latitude (°)</span><input type="number" min={-90} max={90} step="any" value={customLat} onChange={(event) => { setSelectedTerrainRegionId(""); setCustomLat(event.target.value); }} /></label>
      <label className="control-field"><span>East longitude (°)</span><input type="number" min={-180} max={360} step="any" value={customLon} onChange={(event) => { setSelectedTerrainRegionId(""); setCustomLon(event.target.value); }} /></label>
      <label className="control-field"><span>Elevation (m)</span><input type="number" min={-12000} max={12000} step="any" value={customElevation} onChange={(event) => { setSelectedTerrainRegionId(""); setCustomElevation(event.target.value); }} /></label>
      <p className="custom-terrain-note">Tile-center presets are data sample locations, not surveyed landing sites. When terrain is enabled, the app uses LOLA only if a complete ray radius is covered.</p>
    </div>}
    <div className="mission-controls-footer"><span><span className="status-dot" /> {props.selectedSiteIds.length + (customEnabled ? 1 : 0)} site{props.selectedSiteIds.length + (customEnabled ? 1 : 0) === 1 ? "" : "s"} selected</span><span>Local date/time is sent as UTC · max 5,000 samples</span></div>
    {validation && <div className="notice notice-error">{validation}</div>}
  </section>;
}
