import { CircleHelp } from "lucide-react";
import type { Model } from "../types";
import { money, count, fullDate } from "../format";

export default function ModelView({ model }: { model: Model | null }) {
  return (
    <section className="inner-page">
      <h1>About the model</h1>
      <p className="page-lead">
        This model learns from advertised rents. Use its estimates as context
        alongside an in-person viewing.
      </p>
      {model?.preview_only && (
        <p className="stale-notice" role="status">
          Preview model with valuation dates. Chronological results are used for
          model development with data through November 2026; they are not an
          independent future evaluation.
        </p>
      )}
      <div className="model-stats">
        <article>
          <span>
            {model?.preview_only
              ? "Chronological validation error"
              : "Average benchmark error"}
          </span>
          <strong>
            {model ? money(model.benchmark.mae_vnd) : "—"}
            <small> million VND / month</small>
          </strong>
          <p>
            Measured in the original currency across{" "}
            {model?.internal_test_n || "—"}{" "}
            {model?.preview_only
              ? "validation observations."
              : "fixed benchmark listings."}
          </p>
        </article>
        <article>
          <span>Training observations</span>
          <strong>
            {model ? count(model.development_n) : "—"}
            <small> listings</small>
          </strong>
          <p>
            Benchmark listings and their related duplicate groups are excluded
            from training.
          </p>
        </article>
        <article>
          <span>Serving version</span>
          <strong className="version-text">
            {model?.version.slice(0, 8) || "—"}
          </strong>
          <p>Evaluated on {model ? fullDate(model.evaluated_at) : "—"}.</p>
        </article>
      </div>
      <div className="model-explanation">
        <div>
          <h2>Bedrooms are not beds</h2>
          <p>
            Enter 0 for a studio with no separate bedroom. An unspecified count
            stays missing. For rooms, the bedroom count is only used when
            coverage is sufficient and the model includes that feature. Each
            result lists the features it actually uses.
          </p>
          {model?.behavior && (
            <p className="behavior-note">
              {count(model.behavior.checked_rows)} combinations checked ·{" "}
              {model.behavior.violations} violations where increasing area or
              bedrooms lowers the prediction.
            </p>
          )}
          <h2>Which details affect the estimate?</h2>
          <p>
            Property type, district and area form the core inputs. Bedrooms and
            furnishing are used when included in the model's feature set.
          </p>
          {model?.feature_schema.includes("valuation_date") && (
            <p>
              The valuation date defaults to today in Hanoi. You can choose
              within two calendar months of the current month. Time features are
              learned from observed prices; adding a date does not mean rent
              always increases over time.
            </p>
          )}
          {model?.feature_schema.includes("ward_key") && (
            <p>
              This preview also uses ward, development and bathroom counts.
              Leave uncertain details unspecified; they are handled using the
              model's learned missing-value treatment.
            </p>
          )}
          <h2>How are new models selected?</h2>
          <p>
            The regular pipeline checks the data, trains candidates and compares
            overall and per-category errors. A candidate replaces the serving
            model only when it meets the predefined criteria.
          </p>
          <h2>What the model cannot see</h2>
          <p>
            Exact location, condition, natural light, amenities, service charges
            and negotiation can make a substantial difference. The data does not
            cover detached houses or sale prices.
          </p>
        </div>
        <aside>
          <CircleHelp size={25} />
          <h3>Understanding the error</h3>
          <p>
            MAE is the average absolute difference between predicted and
            advertised rents in validation. The error for an individual property
            can be larger.
          </p>
          <p>
            {model?.preview_only
              ? "Chronological folds train on earlier observations and separate duplicate groups. November has already been used during development."
              : "The benchmark is reused for regression checks. Its results do not establish accuracy for a future batch of listings."}
          </p>
          {model &&
            Object.entries(model.category_metrics).map(([c, s]) => (
              <div className="source-row" key={c}>
                <span>{c === "nha_tro" ? "Room" : "Apartment"}</span>
                <strong>{money(s.mae_vnd)} million VND</strong>
              </div>
            ))}
        </aside>
      </div>
    </section>
  );
}
