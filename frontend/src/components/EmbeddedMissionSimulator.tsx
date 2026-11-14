import type { MissionPlan } from "../types";

export function EmbeddedMissionSimulator({ plan }: { plan: MissionPlan }) {
  return <section className="panel simulator-panel embedded-simulator-panel">
    <div className="simulator-canvas-frame existing-simulator-frame">
      <iframe
        title={`Existing Lunar Horizon Canvas simulator for ${plan.site.name}`}
        srcDoc={plan.simulator_html}
        sandbox="allow-scripts"
        loading="eager"
      />
    </div>
  </section>;
}
