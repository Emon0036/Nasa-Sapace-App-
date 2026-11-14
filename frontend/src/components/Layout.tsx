import { useState } from "react";
import {
  Activity, BarChart3, CalendarDays, ChevronLeft, Compass, Menu,
  Orbit, Satellite, Sparkles, Telescope, X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type PageKey = "overview" | "site" | "seasonal" | "compare" | "simulator" | "recommendations";

const NAV_ITEMS: { key: PageKey; label: string; icon: LucideIcon; section: string }[] = [
  { key: "overview", label: "Mission overview", icon: BarChart3, section: "Operations" },
  { key: "site", label: "Site analysis", icon: Telescope, section: "Operations" },
  { key: "seasonal", label: "Seasonal sweep", icon: CalendarDays, section: "Analysis" },
  { key: "compare", label: "Scenario compare", icon: Compass, section: "Analysis" },
  { key: "simulator", label: "Mission simulator", icon: Orbit, section: "Mission tools" },
  { key: "recommendations", label: "ML recommendations", icon: Sparkles, section: "Mission tools" },
];

const PAGE_LABELS: Record<PageKey, string> = Object.fromEntries(NAV_ITEMS.map((item) => [item.key, item.label])) as Record<PageKey, string>;

interface LayoutProps {
  page: PageKey;
  onPageChange: (page: PageKey) => void;
  backendOnline: boolean | null;
  backendName?: string;
  children: React.ReactNode;
}

export function Layout({ page, onPageChange, backendOnline, backendName, children }: LayoutProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const sections = [...new Set(NAV_ITEMS.map((item) => item.section))];

  const choosePage = (next: PageKey) => {
    onPageChange(next);
    setMobileOpen(false);
  };

  return (
    <div className="app-shell">
      {mobileOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`} aria-label="Main navigation">
        <div className="brand-block">
          <div className="brand-mark"><Orbit size={19} strokeWidth={1.8} /></div>
          <div><div className="brand-title">LUNAR HORIZON</div><div className="brand-subtitle">MISSION PLANNING SYSTEM</div></div>
          <button className="icon-button mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X size={18} /></button>
        </div>
        <div className="mission-tag"><span className="status-dot" /> SOUTH POLE OPERATIONS</div>
        <nav className="nav-groups">
          {sections.map((section) => (
            <div className="nav-section" key={section}>
              <div className="nav-section-label">{section}</div>
              {NAV_ITEMS.filter((item) => item.section === section).map(({ key, label, icon: Icon }) => (
                <button key={key} className={`nav-item ${page === key ? "nav-item-active" : ""}`} onClick={() => choosePage(key)} aria-current={page === key ? "page" : undefined}>
                  <Icon size={16} strokeWidth={1.8} /><span>{label}</span>{page === key && <span className="nav-active-mark" />}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="footer-orbit"><Satellite size={16} /><span>SCIENCE SYSTEMS</span><Activity size={13} className="footer-signal" /></div>
          <p>JPL Horizons · NAIF SPICE</p>
          <p>Research prototype · v1.0</p>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <button className="icon-button menu-toggle" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={19} /></button>
          <div className="breadcrumb"><span>MISSION CONTROL</span><ChevronLeft size={13} className="breadcrumb-chevron" /><strong>{PAGE_LABELS[page]}</strong></div>
          <div className="topbar-status">
            <div className={`connection-pill ${backendOnline ? "connected" : backendOnline === false ? "disconnected" : "checking"}`}>
              <span className="status-dot" />{backendOnline ? "API CONNECTED" : backendOnline === false ? "API OFFLINE" : "CONNECTING"}
            </div>
            <div className="backend-label">{backendName ?? "LUNAR HORIZON"}</div>
          </div>
        </header>
        <main className="main-content">{children}</main>
      </section>
    </div>
  );
}
