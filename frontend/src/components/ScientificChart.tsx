import { useEffect, useRef, useState } from "react";
import type { Config, Data, Layout } from "plotly.js";

interface ScientificChartProps {
  data: Data[];
  layout?: Partial<Layout>;
  className?: string;
  ariaLabel: string;
  height?: number;
}

export function ScientificChart({ data, layout = {}, className = "", ariaLabel, height = 320 }: ScientificChartProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [message, setMessage] = useState("Loading chart renderer…");

  useEffect(() => {
    let cancelled = false;
    let chart: typeof import("plotly.js") | null = null;
    const host = hostRef.current;

    if (!host) return undefined;
    setMessage("Loading chart renderer…");
    void import("plotly.js-cartesian-dist-min").then(async (module) => {
      if (cancelled || !hostRef.current) return;
      chart = module.default;
      const baseLayout: Partial<Layout> = {
        autosize: true,
        height,
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "Inter, ui-sans-serif, system-ui", size: 13, color: "#c5d1df" },
        margin: { l: 48, r: 18, t: 16, b: 42 },
        legend: { orientation: "h", y: -0.22 },
        xaxis: { gridcolor: "rgba(148,163,184,.12)", zerolinecolor: "rgba(148,163,184,.18)" },
        yaxis: { gridcolor: "rgba(148,163,184,.12)", zerolinecolor: "rgba(148,163,184,.18)" },
      };
      try {
        await chart.react(hostRef.current, data, { ...baseLayout, ...layout }, {
          responsive: true,
          displaylogo: false,
          modeBarButtonsToRemove: ["lasso2d", "select2d"],
        } satisfies Partial<Config>);
        if (!cancelled) setMessage("");
      } catch (error) {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Chart could not be rendered.");
      }
    }).catch((error: unknown) => {
      if (!cancelled) setMessage(error instanceof Error ? error.message : "Chart renderer failed to load.");
    });

    const resizeObserver = new ResizeObserver(() => {
      if (chart && hostRef.current) void chart.Plots.resize(hostRef.current);
    });
    resizeObserver.observe(host);
    return () => {
      cancelled = true;
      resizeObserver.disconnect();
      if (chart && hostRef.current) chart.purge(hostRef.current);
    };
  }, [data, layout, height]);

  return (
    <div className={`chart-wrap ${className}`} role="img" aria-label={ariaLabel}>
      <div ref={hostRef} className="chart-host" />
      {message && <div className="chart-status" role="status">{message}</div>}
    </div>
  );
}
