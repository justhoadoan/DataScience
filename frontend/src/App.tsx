import { useEffect, useState } from "react";
import {
  House,
  ChartNoAxesCombined,
  CircleHelp,
  ArrowUpRight,
  RefreshCw,
  MapPin,
} from "lucide-react";
import type { Schema, Model, Market } from "./types";
import { fullDate } from "./format";
import MarketView from "./components/MarketView";
import ModelView from "./components/ModelView";
import EstimatorWorkspace from "./components/EstimatorWorkspace";

export default function App() {
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
        throw new Error("Dịch vụ chưa sẵn sàng. Vui lòng thử lại.");
      const [s, m, k] = await Promise.all(responses.map((r) => r.json()));
      setSchema(s);
      setModel(m);
      setMarket(k);
    } catch (e) {
      setLoadError(
        e instanceof Error ? e.message : "Không thể kết nối dịch vụ.",
      );
    }
  }
  useEffect(() => {
    void load();
  }, []);
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Đến nội dung chính
      </a>
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => setView("estimate")}
          aria-label="Hanoi Rent, trang chủ"
        >
          <House size={22} />
          <span>
            hanoirent<span className="brand-dot">.</span>
          </span>
        </button>
        <div className="workspace-name">
          <MapPin size={14} />
          Thị trường thuê · Hà Nội
        </div>
        <nav aria-label="Điều hướng chính">
          {(
            [
              ["estimate", "Ước tính giá", House],
              ["market", "Thị trường", ChartNoAxesCombined],
              ["model", "Về mô hình", CircleHelp],
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
          <span>Dữ liệu đến</span>
          <strong>{market ? fullDate(market.posting_end) : "Đang tải…"}</strong>
          <p>Giá chào thuê từ Nhatot và Alonhadat.</p>
          <button className="text-link" onClick={() => setView("model")}>
            Cách đọc kết quả <ArrowUpRight size={14} />
          </button>
        </div>
      </aside>
      <div className="app-content">
        <header className="topbar">
          <span>
            Hà Nội{" "}
            <span className="breadcrumb">
              /{" "}
              {view === "estimate"
                ? "Ước tính"
                : view === "market"
                  ? "Thị trường"
                  : "Mô hình"}
            </span>
          </span>
          <span className="topbar-scope">Căn hộ & phòng trọ</span>
        </header>
        <main id="main" className="main-canvas">
          {loadError && (
            <div role="alert" className="connection-error">
              <span>{loadError}</span>
              <button onClick={() => void load()}>
                <RefreshCw size={15} />
                Thử lại
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
            <span>Giá chào tham khảo · Không bao gồm nhà riêng</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
