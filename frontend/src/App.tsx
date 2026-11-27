import { useEffect, useState } from "react";
import {
  House,
  ChartNoAxesCombined,
  CircleHelp,
  ArrowUpRight,
  RefreshCw,
  MapPin,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import type { Schema, Model, Market } from "./types";
import { fullDate } from "./format";
import MarketView from "./components/MarketView";
import ModelView from "./components/ModelView";
import EstimatorWorkspace from "./components/EstimatorWorkspace";
import { useTheme } from "./useTheme";

export default function App() {
  const { theme, setTheme } = useTheme();
  const [view, setView] = useState<"estimate" | "market" | "model">("estimate");
  const [schema, setSchema] = useState<Schema | null>(null);
  const [model, setModel] = useState<Model | null>(null);
  const [market, setMarket] = useState<Market | null>(null);
  const [loadError, setLoadError] = useState("");
  async function load() {
    setLoadError("");
    try {
      const responses = await Promise.all(
        ["/api/schema", "/api/model", "/api/market"].map((url) => fetch(url)),
      );
      if (responses.some((r) => !r.ok))
        throw new Error("The service is unavailable. Please try again.");
      const [s, m, k] = await Promise.all(responses.map((r) => r.json()));
      setSchema(s);
      setModel(m);
      setMarket(k);
    } catch (e) {
      setLoadError(
        e instanceof Error ? e.message : "Unable to connect to the service.",
      );
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => setView("estimate")}
          aria-label="Hanoi Rent home"
        >
          <House size={22} />
          <span>
            hanoirent<span className="brand-dot">.</span>
          </span>
        </button>
        <div className="workspace-name">
          <MapPin size={14} />
          Hanoi rental market
        </div>
        <nav aria-label="Main navigation">
          {(
            [
              ["estimate", "Rent estimator", House],
              ["market", "Market overview", ChartNoAxesCombined],
              ["model", "About the model", CircleHelp],
            ] as const
          ).map(([key, label, Icon]) => (
            <button
              key={key}
              className={view === key ? "nav-item active" : "nav-item"}
              onClick={() => setView(key)}
              aria-current={view === key ? "page" : undefined}
            >
              <Icon size={18} />
              <span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span>Latest listing date</span>
          <strong>{market ? fullDate(market.posting_end) : "Loading…"}</strong>
          <p>
            Asking rents from{" "}
            {market
              ? Object.keys(market.source_counts)
                  .map(
                    (s) =>
                      ({
                        nhatot: "Nhatot",
                        alonhadat: "Alonhadat",
                        phongtro123: "Phongtro123",
                      })[s] || s,
                  )
                  .join(", ")
              : "rental listings"}
            .
          </p>
          <button className="text-link" onClick={() => setView("model")}>
            How to read your estimate <ArrowUpRight size={14} />
          </button>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <span>
            Hanoi{" "}
            <span className="breadcrumb">
              /{" "}
              {view === "estimate"
                ? "Estimator"
                : view === "market"
                  ? "Market"
                  : "Model"}
            </span>
          </span>
          <div className="theme-picker" role="group" aria-label="Appearance">
            {(
              [
                ["light", "Light", Sun],
                ["dark", "Dark", Moon],
                ["system", "System", Monitor],
              ] as const
            ).map(([value, label, Icon]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTheme(value)}
                aria-pressed={theme === value}
                aria-label={`${label} theme`}
                title={`${label} theme`}
              >
                <Icon size={15} />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </header>
        <main id="main" className="main-canvas">
          {loadError && (
            <div role="alert" className="connection-error">
              <span>{loadError}</span>
              <button onClick={() => void load()}>
                <RefreshCw size={15} />
                Try again
              </button>
            </div>
          )}
          <div hidden={view !== "estimate"}>
            <EstimatorWorkspace
              schema={schema}
              model={model}
              market={market}
              onModel={() => setView("model")}
            />
          </div>
          {view === "market" && (
            <MarketView market={market} loadError={loadError} />
          )}
          {view === "model" && <ModelView model={model} />}
          <footer className="page-footer">
            <span>Hanoi Rent Insight</span>
            <span>Asking rents, for reference · Apartments & rooms only</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
