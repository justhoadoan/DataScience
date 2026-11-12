import { useState } from "react";
import { Database } from "lucide-react";
import type { Category, Market } from "../types";
import { money, count, fullDate } from "../format";

export default function MarketView({
  market,
  loadError,
}: {
  market: Market | null;
  loadError: string;
}) {
  const [marketCategory, setMarketCategory] =
    useState<Category>("can_ho_chung_cu");
  const districts = (market?.districts || [])
    .filter((r) => r.category === marketCategory && r.n >= 10)
    .sort((a, b) => b.n - a.n);
  return (
    <section className="inner-page">
      <h1>Thị trường thuê</h1>
      <p className="page-lead">
        Giá chào trong mẫu tin đã qua kiểm tra. Số liệu phản ánh cơ cấu nguồn
        thu thập và chưa đại diện cho toàn Hà Nội.
      </p>
      <div className="segmented">
        {(["can_ho_chung_cu", "nha_tro"] as const).map((c) => (
          <button
            key={c}
            className={marketCategory === c ? "selected" : ""}
            onClick={() => setMarketCategory(c)}
          >
            {c === "can_ho_chung_cu" ? "Căn hộ / chung cư" : "Phòng trọ"}
          </button>
        ))}
      </div>
      <div className="market-layout">
        <div className="market-table">
          <div className="table-heading">
            <h2>Giá chào theo khu vực</h2>
            <span>triệu đồng / tháng</span>
          </div>
          <div className="district-grid table-head">
            <span>Quận / huyện</span>
            <span>Trung vị</span>
            <span>50% tin ở giữa</span>
            <span>Số tin</span>
          </div>
          {districts.map((d) => (
            <div className="district-grid" key={d.district}>
              <strong>{d.district}</strong>
              <span>{money(d.median_vnd)}</span>
              <span className="range">
                {money(d.q25_vnd)} – {money(d.q75_vnd)}
              </span>
              <span>{count(d.n)}</span>
            </div>
          ))}
          {!districts.length && (
            <p className="table-empty">
              {loadError ? "Chưa tải được dữ liệu." : "Đang tải dữ liệu…"}
            </p>
          )}
          <p className="table-note">
            Chỉ hiển thị nhóm có từ 10 tin. Nhóm dưới 30 tin chỉ mang tính khám
            phá; khác biệt diện tích và nội thất chưa được kiểm soát.
          </p>
        </div>
        <aside className="market-aside">
          <Database size={26} />
          <h3>Đọc số liệu đúng cách</h3>
          <p>
            Trung vị là mức nằm giữa mẫu tin, không phải giá chuẩn cho mọi căn
            trong quận.
          </p>
          <div className="aside-stat">
            <strong>{market ? count(market.eligible_rows) : "—"}</strong>
            <span>tin trong tập giá</span>
          </div>
          {market &&
            Object.entries(market.source_counts).map(([s, n]) => (
              <div className="source-row" key={s}>
                <span>{s === "nhatot" ? "Nhatot" : "Alonhadat"}</span>
                <strong>{count(n)}</strong>
              </div>
            ))}
          <p className="field-help">
            Khoảng ngày đăng:{" "}
            {market
              ? `${fullDate(market.posting_start)} – ${fullDate(market.posting_end)}`
              : "—"}
          </p>
        </aside>
      </div>
    </section>
  );
}
