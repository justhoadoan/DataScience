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
      <h1>Market overview</h1>
      <p className="page-lead">
        Explore asking rents from checked listings. This sample reflects the
        sources collected and does not represent all of Hanoi.
      </p>
      <div className="segmented">
        {(["can_ho_chung_cu", "nha_tro"] as const).map((c) => (
          <button
            key={c}
            className={marketCategory === c ? "selected" : ""}
            aria-pressed={marketCategory === c}
            onClick={() => setMarketCategory(c)}
          >
            {c === "can_ho_chung_cu" ? "Apartment" : "Room"}
          </button>
        ))}
      </div>
      <div className="market-layout">
        <div className="market-table">
          <div className="table-heading">
            <h2>Asking rents by district</h2>
            <span>million VND / month</span>
          </div>
          <div className="district-grid table-head">
            <span>District</span>
            <span>Median</span>
            <span>Middle 50%</span>
            <span>Listings</span>
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
              {loadError
                ? "Data could not be loaded. Use Try again above."
                : "Loading market data…"}
            </p>
          )}
          <p className="table-note">
            Only groups with at least 10 listings are shown. Groups below 30 are
            exploratory; area and furnishing differences are not controlled.
          </p>
        </div>
        <aside className="market-aside">
          <Database size={26} />
          <h3>Reading the market</h3>
          <p>
            The median is the middle asking rent in the sample, not a standard
            price for every property in a district.
          </p>
          <div className="aside-stat">
            <strong>{market ? count(market.eligible_rows) : "—"}</strong>
            <span>listings in the price sample</span>
          </div>
          {market &&
            Object.entries(market.source_counts).map(([s, n]) => (
              <div className="source-row" key={s}>
                <span>
                  {{
                    nhatot: "Nhatot",
                    alonhadat: "Alonhadat",
                    phongtro123: "Phongtro123",
                  }[s] || s}
                </span>
                <strong>{count(n)}</strong>
              </div>
            ))}
          <p className="field-help">
            Listing dates:{" "}
            {market
              ? `${fullDate(market.posting_start)} – ${fullDate(market.posting_end)}`
              : "—"}
          </p>
        </aside>
      </div>
    </section>
  );
}
