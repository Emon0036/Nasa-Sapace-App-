import type { ReactNode } from "react";
import { ArrowDownToLine, Database, Orbit } from "lucide-react";

export function SectionTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <div className="section-heading">
      <div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h2>{title}</h2></div>
      {children && <div className="section-heading-actions">{children}</div>}
    </div>
  );
}

export function MetricCard({ label, value, detail, tone = "neutral", icon }: {
  label: string; value: string; detail?: string; tone?: "neutral" | "sun" | "earth" | "good" | "alert"; icon?: ReactNode;
}) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <div className="metric-top"><span>{label}</span>{icon && <span className="metric-icon">{icon}</span>}</div>
      <div className="metric-value">{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </article>
  );
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <div className="empty-icon"><Orbit size={20} /></div>
      <h3>{title}</h3><p>{detail}</p>{action}
    </div>
  );
}

export function SourceBadge({ label, tone = "neutral" }: { label: string; tone?: "neutral" | "good" | "warn" }) {
  const displayLabel = label === "dem"
    ? "LOLA terrain"
    : label === "geometric"
      ? "Geometric horizon"
      : label === "synthetic"
        ? "Illustrative only"
        : label;
  return <span className={`source-badge source-${tone}`}><Database size={12} />{displayLabel}</span>;
}

export function DownloadButton({ onClick, label = "Export CSV" }: { onClick: () => void; label?: string }) {
  return <button className="button button-secondary button-small" onClick={onClick}><ArrowDownToLine size={14} />{label}</button>;
}
