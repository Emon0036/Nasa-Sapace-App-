import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { MissionPlan, MissionPhase } from "../types";

export type MissionCameraMode = "overview" | "follow" | "launch" | "orbit" | "descent" | "surface";

interface MissionScene3DProps {
  plan: MissionPlan;
  seconds: number;
  phase: MissionPhase;
  cameraMode: MissionCameraMode;
}

interface SceneRuntime {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  earth: THREE.Mesh;
  moon: THREE.Mesh;
  spacecraft: THREE.Group;
  spacecraftLabel: THREE.Sprite;
  engine: THREE.PointLight;
  launchPath: THREE.Mesh;
  transitPath: THREE.Mesh;
  orbitPath: THREE.Mesh;
  descentPath: THREE.Mesh;
  surfacePath: THREE.Mesh;
  landingMarker: THREE.Mesh;
  landingTarget: THREE.Vector3;
  launchCurve: THREE.Curve<THREE.Vector3>;
  transitCurve: THREE.Curve<THREE.Vector3>;
  orbitCurve: THREE.Curve<THREE.Vector3>;
  descentCurve: THREE.Curve<THREE.Vector3>;
  lookAt: THREE.Vector3;
  resizeObserver: ResizeObserver;
  frame: number;
}

const EARTH_CENTER = new THREE.Vector3(-7.1, 0, 0);
const MOON_CENTER = new THREE.Vector3(7.15, 0, 0);
const EARTH_RADIUS = 2.85;
const MOON_RADIUS = 1.82;
const LOCAL_LANDING = new THREE.Vector3(0.16, -0.47, 1.39).normalize().multiplyScalar(MOON_RADIUS + 0.035);

function seededRandom(seed: number) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function textureFromCanvas(canvas: HTMLCanvasElement, repeat = false) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  if (repeat) texture.wrapS = THREE.RepeatWrapping;
  return texture;
}

function createGlowTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  const glow = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
  glow.addColorStop(0, "rgba(255,255,255,.88)");
  glow.addColorStop(.18, "rgba(255,255,255,.5)");
  glow.addColorStop(.55, "rgba(255,255,255,.12)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, 128, 128);
  return textureFromCanvas(canvas);
}

function createLabel(text: string, color: string, labelWidth = 3.7, labelHeight = .72) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 100;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "rgba(3,10,20,.76)";
  ctx.strokeStyle = "rgba(125,177,230,.48)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(4, 4, 504, 92, 22);
  ctx.fill();
  ctx.stroke();
  ctx.font = "700 58px Inter, Arial, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.fillText(text, 256, 50);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: textureFromCanvas(canvas), transparent: true, depthTest: false }));
  sprite.scale.set(labelWidth, labelHeight, 1);
  return sprite;
}

function makePath(curve: THREE.Curve<THREE.Vector3>, color: string, radius: number, opacity: number) {
  const mesh = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 128, radius, 8, false),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false }),
  );
  return mesh;
}

function makeOrbitCurve() {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= 180; i += 1) {
    const angle = (i / 180) * Math.PI * 2;
    points.push(new THREE.Vector3(MOON_CENTER.x + Math.cos(angle) * 2.25, Math.sin(angle) * 1.6 + .25, Math.sin(angle) * .22));
  }
  return new THREE.CatmullRomCurve3(points, true, "catmullrom", .15);
}

function makeSpacecraft() {
  const group = new THREE.Group();
  const hull = new THREE.MeshStandardMaterial({ color: "#d7e2ee", metalness: .62, roughness: .32 });
  const darkHull = new THREE.MeshStandardMaterial({ color: "#64768a", metalness: .55, roughness: .42 });
  const gold = new THREE.MeshStandardMaterial({ color: "#efb85b", metalness: .5, roughness: .4 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(.09, .105, .56, 14), hull);
  body.rotation.z = -Math.PI / 2;
  group.add(body);
  const nose = new THREE.Mesh(new THREE.ConeGeometry(.105, .28, 14), hull);
  nose.rotation.z = -Math.PI / 2;
  nose.position.x = .41;
  group.add(nose);
  const engineBell = new THREE.Mesh(new THREE.CylinderGeometry(.075, .12, .18, 12), darkHull);
  engineBell.rotation.z = -Math.PI / 2;
  engineBell.position.x = -.36;
  group.add(engineBell);
  const window = new THREE.Mesh(new THREE.SphereGeometry(.07, 12, 10), new THREE.MeshStandardMaterial({ color: "#6ec8ff", emissive: "#1b6899", metalness: .25, roughness: .2 }));
  window.position.set(.05, .075, .065);
  group.add(window);
  for (const side of [-1, 1]) {
    const fin = new THREE.Mesh(new THREE.BoxGeometry(.2, .035, .25), gold);
    fin.position.set(-.17, 0, side * .15);
    group.add(fin);
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(.018, .024, .29, 8), darkHull);
    leg.position.set(-.08, -.17, side * .12);
    leg.rotation.z = -.28;
    group.add(leg);
  }
  const engineGlow = new THREE.Mesh(new THREE.ConeGeometry(.11, .5, 12), new THREE.MeshBasicMaterial({ color: "#5bbcff", transparent: true, opacity: .68, blending: THREE.AdditiveBlending, depthWrite: false }));
  engineGlow.rotation.z = Math.PI / 2;
  engineGlow.position.x = -.62;
  group.add(engineGlow);
  group.userData.engineGlow = engineGlow;
  const aura = new THREE.Sprite(new THREE.SpriteMaterial({ map: createGlowTexture(), color: "#62bdff", opacity: .6, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  aura.scale.set(.42, .42, 1);
  group.add(aura);
  group.scale.setScalar(2.15);
  return group;
}

function clamp01(value: number) {
  return Math.max(0, Math.min(1, value));
}

function phaseProgress(phase: MissionPhase, seconds: number) {
  return clamp01((seconds - phase.start_seconds) / Math.max(1, phase.end_seconds - phase.start_seconds));
}

function flightPosition(plan: MissionPlan, seconds: number, runtime: SceneRuntime) {
  const phase = plan.phases.find((entry, index) => seconds >= entry.start_seconds && (seconds < entry.end_seconds || index === plan.phases.length - 1)) ?? plan.phases[0];
  const p = phaseProgress(phase, seconds);
  let curve: THREE.Curve<THREE.Vector3>;
  if (phase.name === "LAUNCH") curve = runtime.launchCurve;
  else if (phase.name === "TRANSIT") curve = runtime.transitCurve;
  else if (phase.name === "LUNAR ORBIT") curve = runtime.orbitCurve;
  else if (phase.name === "POWERED DESCENT") curve = runtime.descentCurve;
  else return { phase, position: runtime.landingTarget.clone().add(new THREE.Vector3(0, .16, 0)), tangent: new THREE.Vector3(0, 1, 0) };
  const pathProgress = phase.name === "LUNAR ORBIT" ? p : p;
  return { phase, position: curve.getPointAt(pathProgress), tangent: curve.getTangentAt(pathProgress).normalize() };
}

function cameraPose(mode: MissionCameraMode, craft: THREE.Vector3, tangent: THREE.Vector3) {
  switch (mode) {
    case "follow":
      return { position: craft.clone().addScaledVector(tangent, -4).add(new THREE.Vector3(0, 2.4, 9)), target: craft.clone() };
    case "launch":
      return { position: new THREE.Vector3(-10, 2.4, 10), target: new THREE.Vector3(-6.3, .25, 0) };
    case "orbit":
      return { position: new THREE.Vector3(7.3, 3.5, 9), target: MOON_CENTER.clone() };
    case "descent":
      return { position: new THREE.Vector3(5.9, 2.2, 7.5), target: MOON_CENTER.clone().add(LOCAL_LANDING) };
    case "surface":
      return { position: new THREE.Vector3(9.6, .55, 4.5), target: MOON_CENTER.clone().add(LOCAL_LANDING) };
    default:
      return { position: new THREE.Vector3(0, .15, 22.5), target: new THREE.Vector3(0, 0, 0) };
  }
}

export function MissionScene3D({ plan, seconds, phase, cameraMode }: MissionScene3DProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<SceneRuntime | null>(null);
  const stateRef = useRef({ seconds, phase, cameraMode });
  const [renderError, setRenderError] = useState("");
  stateRef.current = { seconds, phase, cameraMode };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    let disposed = false;
    let runtime: SceneRuntime;
    try {
      const scene = new THREE.Scene();
      scene.background = new THREE.Color("#030813");
      scene.fog = new THREE.FogExp2("#030813", .0065);
      const camera = new THREE.PerspectiveCamera(38, 1, .1, 300);
      camera.position.set(0, .15, 26);
      const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.18;
      renderer.domElement.className = "mission-three-canvas";
      renderer.domElement.setAttribute("aria-label", "Animated Earth-to-Moon mission route with illustrative spacecraft trajectory");
      host.appendChild(renderer.domElement);

      scene.add(new THREE.AmbientLight("#9db9da", .68));
      const sun = new THREE.DirectionalLight("#fff1d6", 3.05);
      sun.position.set(-8, 8, 13);
      scene.add(sun);
      const blueFill = new THREE.DirectionalLight("#4b86c4", .45);
      blueFill.position.set(7, -3, -6);
      scene.add(blueFill);

      const starsGeometry = new THREE.BufferGeometry();
      const starRandom = seededRandom(127);
      const starPositions = new Float32Array(2200 * 3);
      const starColors = new Float32Array(2200 * 3);
      for (let i = 0; i < 2200; i += 1) {
        const radius = 55 + starRandom() * 100;
        const theta = starRandom() * Math.PI * 2;
        const z = starRandom() * 2 - 1;
        const ring = Math.sqrt(1 - z * z);
        starPositions[i * 3] = radius * ring * Math.cos(theta);
        starPositions[i * 3 + 1] = radius * z;
        starPositions[i * 3 + 2] = radius * ring * Math.sin(theta);
        const tint = .66 + starRandom() * .34;
        starColors[i * 3] = tint * .82;
        starColors[i * 3 + 1] = tint * .9;
        starColors[i * 3 + 2] = tint;
      }
      starsGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
      starsGeometry.setAttribute("color", new THREE.BufferAttribute(starColors, 3));
      const stars = new THREE.Points(starsGeometry, new THREE.PointsMaterial({ size: .075, vertexColors: true, transparent: true, opacity: .88, sizeAttenuation: true }));
      scene.add(stars);

      const earthMaterial = new THREE.MeshStandardMaterial({ color: "#3c79a8", roughness: .88, metalness: .03 });
      const moonMaterial = new THREE.MeshStandardMaterial({ color: "#aaabad", roughness: 1, metalness: 0 });
      const earth = new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS, 96, 64), earthMaterial);
      earth.position.copy(EARTH_CENTER);
      earth.rotation.z = -.18;
      scene.add(earth);
      const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS * 1.07, 64, 48), new THREE.MeshBasicMaterial({ color: "#399dff", transparent: true, opacity: .13, side: THREE.BackSide, depthWrite: false }));
      atmosphere.position.copy(EARTH_CENTER);
      scene.add(atmosphere);
      const moon = new THREE.Mesh(new THREE.SphereGeometry(MOON_RADIUS, 96, 64), moonMaterial);
      moon.position.copy(MOON_CENTER);
      moon.rotation.z = .08;
      scene.add(moon);
      const textureLoader = new THREE.TextureLoader();
      const replaceWithBundledTexture = (material: THREE.MeshStandardMaterial, url: string) => {
        const fallback = material.map;
        textureLoader.load(url, (texture) => {
          if (disposed) {
            texture.dispose();
            return;
          }
          texture.colorSpace = THREE.SRGBColorSpace;
          texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
          material.map = texture;
          material.color.set("#ffffff");
          material.needsUpdate = true;
          fallback?.dispose();
        }, undefined, () => {
          // The bundled procedural texture remains available if an asset is missing.
        });
      };
      replaceWithBundledTexture(earthMaterial, "/textures/earth-blue-marble-2048.png");
      replaceWithBundledTexture(moonMaterial, "/textures/moon-lroc-color-2k.jpg");
      scene.add(createLabel("EARTH · departure", "#bfe2ff").translateX(EARTH_CENTER.x).translateY(-3.15));
      scene.add(createLabel("MOON · south pole", "#e8edf4").translateX(MOON_CENTER.x).translateY(-2.25));

      const landingTarget = MOON_CENTER.clone().add(LOCAL_LANDING);
      const earthDeparture = EARTH_CENTER.clone().add(new THREE.Vector3(2.5, .4, 1.65));
      const launchCurve = new THREE.CubicBezierCurve3(
        earthDeparture,
        new THREE.Vector3(-5.05, -.75, 1.4),
        new THREE.Vector3(-4.55, .95, .5),
        new THREE.Vector3(-4.15, .65, .12),
      );
      const transitCurve = new THREE.CubicBezierCurve3(
        new THREE.Vector3(-4.15, .65, .12),
        new THREE.Vector3(-2.05, 3.65, .12),
        new THREE.Vector3(2.65, 3.65, .12),
        new THREE.Vector3(MOON_CENTER.x - MOON_RADIUS * .95, .55, .05),
      );
      const orbitCurve = makeOrbitCurve();
      const descentStart = orbitCurve.getPointAt(.86);
      const descentCurve = new THREE.CubicBezierCurve3(
        descentStart,
        new THREE.Vector3(5.15, -1.55, 1.0),
        landingTarget.clone().add(new THREE.Vector3(-.9, .65, .2)),
        landingTarget,
      );
      const surfaceEnd = landingTarget.clone().add(new THREE.Vector3(.34, -.08, 0));
      const surfaceCurve = new THREE.CubicBezierCurve3(landingTarget, landingTarget.clone().add(new THREE.Vector3(.1,.1,0)), surfaceEnd.clone().add(new THREE.Vector3(-.1,.12,0)), surfaceEnd);
      const launchPath = makePath(launchCurve, "#63bfff", .065, .9);
      const transitPath = makePath(transitCurve, "#42d2ff", .07, .94);
      const orbitPath = makePath(orbitCurve, "#c6e4ff", .04, .72);
      const descentPath = makePath(descentCurve, "#ffb45b", .065, .95);
      const surfacePath = makePath(surfaceCurve, "#59ddb0", .045, .8);
      for (const path of [launchPath, transitPath, orbitPath, descentPath, surfacePath]) scene.add(path);

      const landingMarker = new THREE.Mesh(new THREE.RingGeometry(.23, .32, 56), new THREE.MeshBasicMaterial({ color: "#5ce0ae", transparent: true, opacity: .9, side: THREE.DoubleSide, depthWrite: false }));
      landingMarker.position.copy(landingTarget);
      landingMarker.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), LOCAL_LANDING.clone().normalize());
      scene.add(landingMarker);
      const markerGlow = new THREE.PointLight("#54e5b0", 2.2, 2.3);
      markerGlow.position.copy(landingTarget);
      scene.add(markerGlow);

      const spacecraft = makeSpacecraft();
      scene.add(spacecraft);
      const spacecraftLabel = createLabel("SPACECRAFT", "#ffd18a", 2.5, .48);
      scene.add(spacecraftLabel);
      const engine = new THREE.PointLight("#61c4ff", 1.7, 2.4);
      spacecraft.add(engine);
      engine.position.set(-.7, 0, 0);
      const observer = new ResizeObserver(() => {
        const rect = host.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        camera.aspect = rect.width / rect.height;
        camera.updateProjectionMatrix();
        renderer.setSize(rect.width, rect.height, false);
      });
      observer.observe(host);
      runtime = { renderer, scene, camera, earth, moon, spacecraft, spacecraftLabel, engine, launchPath, transitPath, orbitPath, descentPath, surfacePath, landingMarker, landingTarget, launchCurve, transitCurve, orbitCurve, descentCurve, lookAt: new THREE.Vector3(0,0,0), resizeObserver: observer, frame: 0 };
      runtimeRef.current = runtime;

      const draw = () => {
        const current = stateRef.current;
        const flight = flightPosition(plan, current.seconds, runtime);
        spacecraft.position.copy(flight.position);
        spacecraft.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), flight.tangent);
        spacecraft.visible = current.cameraMode !== "surface" || flight.phase.name === "SURFACE OPS";
        spacecraftLabel.visible = spacecraft.visible;
        spacecraftLabel.position.copy(flight.position).add(new THREE.Vector3(0, .78, .28));
        const engineGlow = spacecraft.userData.engineGlow as THREE.Mesh;
        const engineActive = flight.phase.name !== "SURFACE OPS";
        engineGlow.visible = engineActive;
        engine.intensity = engineActive ? 1.2 + .55 * Math.sin(current.seconds * .003) : .15;
        engine.distance = engineActive ? 2.4 : .45;
        const selectedPhase = current.phase.name;
        launchPath.material.opacity = selectedPhase === "LAUNCH" ? .98 : .38;
        transitPath.material.opacity = selectedPhase === "TRANSIT" ? 1 : .42;
        orbitPath.material.opacity = selectedPhase === "LUNAR ORBIT" ? .95 : .46;
        descentPath.material.opacity = selectedPhase === "POWERED DESCENT" ? 1 : .45;
        surfacePath.material.opacity = selectedPhase === "SURFACE OPS" ? .95 : .38;
        earth.rotation.y = .22 + current.seconds * .0000017;
        moon.rotation.y = .16 + current.seconds * .00000022;
        landingMarker.rotation.z = Math.sin(current.seconds * .0009) * .035;
        const pose = cameraPose(current.cameraMode, flight.position, flight.tangent);
        if (current.cameraMode === "overview") pose.position.z = Math.max(22.5, 29.5 / Math.max(.75, camera.aspect));
        camera.position.lerp(pose.position, .055);
        runtime.lookAt.lerp(pose.target, .065);
        camera.lookAt(runtime.lookAt);
        renderer.render(scene, camera);
        runtime.frame = window.requestAnimationFrame(draw);
      };
      const rect = host.getBoundingClientRect();
      camera.aspect = rect.width / Math.max(1, rect.height);
      camera.updateProjectionMatrix();
      renderer.setSize(rect.width, rect.height, false);
      draw();
    } catch (caught) {
      setRenderError(caught instanceof Error ? caught.message : "WebGL mission viewport could not initialize.");
      return undefined;
    }

    return () => {
      disposed = true;
      const active = runtimeRef.current;
      if (!active) return;
      window.cancelAnimationFrame(active.frame);
      active.resizeObserver.disconnect();
      active.scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Points || object instanceof THREE.Sprite) {
          object.geometry?.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => {
            const map = "map" in material ? material.map : null;
            map?.dispose();
            material.dispose();
          });
        }
      });
      active.renderer.dispose();
      active.renderer.domElement.remove();
      runtimeRef.current = null;
    };
  }, [plan]);

  return <div className="mission-scene-3d" data-camera-mode={cameraMode} data-clock-seconds={seconds}>
    <div className="mission-scene-webgl" ref={hostRef} />
    {renderError ? <div className="mission-scene-error" role="alert"><strong>3D viewport unavailable</strong><span>{renderError}</span></div> : null}
    <div className="mission-scene-corner mission-scene-corner-left"><span className="scene-live-dot" />{cameraMode === "overview" ? "MISSION OVERVIEW" : cameraMode.replace("-", " ").toUpperCase()}</div>
    <div className="mission-scene-corner mission-scene-corner-right">NOT TO SCALE · VEHICLE PATH ILLUSTRATIVE</div>
  </div>;
}
