import {
  ArrowRight,
  Info,
  LoaderCircle,
  ArrowUpRight,
  ChevronDown,
} from "lucide-react";
import type { Schema, Model, Market } from "../types";
import { useEstimate } from "../useEstimate";
import { money, count, fullDate } from "../format";
import LayoutPreview from "./LayoutPreview";

const categoryName = (value: string) =>
  value === "can_ho_chung_cu" ? "Apartment" : "Room";
const calendarDate = fullDate;
const bathroomName = (value: string | number) =>
  `${value} bathroom${Number(value) === 1 ? "" : "s"} / WC`;
const bedroomName = (value: string) =>
  value === ""
    ? "Bedrooms not specified"
    : value === "0"
      ? "Studio · no separate bedroom"
      : `${value} separate bedroom${value === "1" ? "" : "s"}`;

export default function EstimatorWorkspace({
  schema,
  model,
  market,
  onModel,
}: {
  schema: Schema | null;
  model: Model | null;
  market: Market | null;
  onModel: () => void;
}) {
  const {
    draft,
    update,
    estimate,
    submitted,
    busy,
    errors,
    submit,
    stale,
    maximum,
    invalidLayout,
    valuationDates,
  } = useEstimate(schema);
  const fields = model?.category_feature_schema[draft.category] || [];
  const bedroomUsed = fields.includes("bedrooms_analysis");
  const sparseBedrooms =
    model?.feature_schema.includes("bedrooms_analysis") && !bedroomUsed;
  return (
    <>
      <div className="screen-heading">
        <div>
          <h1>Rental estimate</h1>
          <p>Estimate an apartment or room using Hanoi's rental listings.</p>
        </div>
        <span className="scope-stamp">
          {market ? count(market.eligible_rows) : "—"} listings in the price
          sample
        </span>
      </div>
      <div className="workspace-grid">
        <form
          className="panel property-form"
          onSubmit={submit}
          noValidate
          aria-busy={busy}
        >
          <div className="panel-heading">
            <h2>Your property</h2>
            <span>* Required</span>
          </div>
          <fieldset className="category-field">
            <legend>Property type *</legend>
            <div className="category-options">
              {(
                schema?.categories || [
                  { value: "can_ho_chung_cu", label: "Apartment" },
                  { value: "nha_tro", label: "Room" },
                ]
              ).map((c) => (
                <label
                  className={
                    draft.category === c.value
                      ? "category-option selected"
                      : "category-option"
                  }
                  key={c.value}
                >
                  <input
                    type="radio"
                    name="category"
                    value={c.value}
                    checked={draft.category === c.value}
                    onChange={() =>
                      update("category", c.value as typeof draft.category)
                    }
                  />
                  <span>{c.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="district">District *</label>
              <div className="select-wrap">
                <select
                  id="district"
                  value={draft.district}
                  onChange={(e) => update("district", e.target.value)}
                  required
                  aria-invalid={!!errors.district}
                  aria-describedby={
                    errors.district ? "district-error" : undefined
                  }
                >
                  <option value="">Select a district</option>
                  {schema?.districts.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </div>
              {errors.district && (
                <p id="district-error" className="field-error">
                  {errors.district}
                </p>
              )}
            </div>
            <div className="field">
              <label htmlFor="area">Usable area *</label>
              <div className="number-wrap">
                <input
                  id="area"
                  type="number"
                  inputMode="decimal"
                  min="6"
                  max="500"
                  step="0.1"
                  value={draft.area}
                  onChange={(e) => update("area", e.target.value)}
                  required
                  aria-invalid={!!errors.area_m2}
                  aria-describedby={errors.area_m2 ? "area-error" : "area-help"}
                />
                <span>m²</span>
              </div>
              <p id="area-help" className="field-help">
                The area of the apartment or room itself.
              </p>
              {errors.area_m2 && (
                <p id="area-error" className="field-error">
                  {errors.area_m2}
                </p>
              )}
            </div>
            <div className="field">
              <label htmlFor="bedrooms">
                Bedrooms <span className="optional-label">Optional</span>
              </label>
              <div className="select-wrap">
                <select
                  id="bedrooms"
                  value={draft.bedrooms}
                  onChange={(e) => update("bedrooms", e.target.value)}
                  aria-invalid={invalidLayout || !!errors.bedrooms}
                  aria-describedby="bedrooms-help bedrooms-error"
                >
                  <option value="">Not specified</option>
                  <option value="0">0 — Studio / open plan</option>
                  {Array.from({ length: maximum }, (_, i) => (
                    <option key={i + 1} value={String(i + 1)}>
                      {i + 1} separate bedroom{i === 0 ? "" : "s"}
                    </option>
                  ))}
                  {invalidLayout && (
                    <option value={draft.bedrooms} disabled>
                      {draft.bedrooms} bedrooms — exceeds area limit
                    </option>
                  )}
                </select>
                <ChevronDown size={15} />
              </div>
              <p id="bedrooms-help" className="field-help">
                Choose 0 for a studio with no separate bedroom.
              </p>
              {(invalidLayout || errors.bedrooms) && (
                <p id="bedrooms-error" role="alert" className="field-error">
                  {errors.bedrooms ||
                    `For ${draft.area} m², this app allows up to ${maximum} separate bedrooms.`}
                </p>
              )}
            </div>
            <div className="field">
              <label htmlFor="furnishing">
                Furnishing <span className="optional-label">Optional</span>
              </label>
              <div className="select-wrap">
                <select
                  id="furnishing"
                  value={draft.furnishing}
                  onChange={(e) => update("furnishing", e.target.value)}
                >
                  {(
                    schema?.furnishing || [
                      { value: "Unknown", label: "Not specified" },
                    ]
                  ).map((f) => (
                    <option key={f.value} value={f.value}>
                      {f.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </div>
            </div>
            {valuationDates && (
              <div className="field">
                <label htmlFor="valuation_date">Valuation date</label>
                <input
                  id="valuation_date"
                  type="date"
                  min={valuationDates.min}
                  max={valuationDates.max}
                  value={draft.valuation_date || valuationDates.today}
                  onChange={(event) =>
                    update("valuation_date", event.target.value)
                  }
                  aria-invalid={!!errors.valuation_date}
                  aria-describedby={
                    errors.valuation_date
                      ? "valuation-date-error valuation-date-help"
                      : "valuation-date-help"
                  }
                />
                <p id="valuation-date-help" className="field-help">
                  Choose between {calendarDate(valuationDates.min)} and{" "}
                  {calendarDate(valuationDates.max)} (Hanoi time).
                </p>
                {errors.valuation_date && (
                  <p
                    id="valuation-date-error"
                    className="field-error"
                    role="alert"
                  >
                    {errors.valuation_date}
                  </p>
                )}
              </div>
            )}
            {schema?.optional.some((field) =>
              ["ward_key", "project_id", "bathrooms"].includes(field),
            ) && (
              <details className="property-details">
                <summary>
                  Location & amenities <span>Optional</span>
                  <small>Ward, development and bathrooms</small>
                </summary>
                <div className="form-grid">
                  {schema?.optional.includes("ward_key") && (
                    <div className="field">
                      <label htmlFor="ward_key">
                        Ward / commune{" "}
                        <span className="optional-label">Optional</span>
                      </label>
                      <div className="select-wrap">
                        <select
                          id="ward_key"
                          value={draft.ward_key}
                          onChange={(e) => update("ward_key", e.target.value)}
                          disabled={!draft.district}
                          aria-invalid={!!errors.ward_key}
                          aria-describedby={
                            errors.ward_key ? "ward-key-error" : undefined
                          }
                        >
                          <option value="Unknown">Not specified</option>
                          {schema.property_options?.wards
                            ?.filter((w) => w.district === draft.district)
                            .map((w) => (
                              <option key={w.value} value={w.value}>
                                {w.label}
                              </option>
                            ))}
                        </select>
                        <ChevronDown size={15} />
                      </div>
                      {errors.ward_key && (
                        <p
                          id="ward-key-error"
                          className="field-error"
                          role="alert"
                        >
                          {errors.ward_key}
                        </p>
                      )}
                    </div>
                  )}
                  {schema?.optional.includes("project_id") && (
                    <div className="field">
                      <label htmlFor="project_id">
                        Development{" "}
                        <span className="optional-label">Optional</span>
                      </label>
                      <div className="select-wrap">
                        <select
                          id="project_id"
                          value={draft.project_id}
                          onChange={(e) => update("project_id", e.target.value)}
                          disabled={!draft.district}
                          aria-invalid={!!errors.project_id}
                          aria-describedby={
                            errors.project_id ? "project-id-error" : undefined
                          }
                        >
                          <option value="Unknown">
                            Not specified / no development
                          </option>
                          {schema.property_options?.projects
                            ?.filter((p) =>
                              p.districts.includes(draft.district),
                            )
                            .map((p) => (
                              <option key={p.value} value={p.value}>
                                {p.label}
                              </option>
                            ))}
                        </select>
                        <ChevronDown size={15} />
                      </div>
                      {errors.project_id && (
                        <p
                          id="project-id-error"
                          className="field-error"
                          role="alert"
                        >
                          {errors.project_id}
                        </p>
                      )}
                    </div>
                  )}
                  {schema?.optional.includes("bathrooms") && (
                    <div className="field">
                      <label htmlFor="bathrooms">
                        Bathrooms / WC{" "}
                        <span className="optional-label">Optional</span>
                      </label>
                      <div className="select-wrap">
                        <select
                          id="bathrooms"
                          value={draft.bathrooms}
                          onChange={(e) => update("bathrooms", e.target.value)}
                          aria-invalid={!!errors.bathrooms}
                          aria-describedby={
                            errors.bathrooms ? "bathrooms-error" : undefined
                          }
                        >
                          <option value="">Not specified</option>
                          {schema.property_options?.bathrooms
                            ?.filter(
                              (n) =>
                                n <= (draft.category === "nha_tro" ? 5 : 10),
                            )
                            .map((n) => (
                              <option key={n} value={String(n)}>
                                {bathroomName(n)}
                              </option>
                            ))}
                        </select>
                        <ChevronDown size={15} />
                      </div>
                      {errors.bathrooms && (
                        <p
                          id="bathrooms-error"
                          className="field-error"
                          role="alert"
                        >
                          {errors.bathrooms}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </details>
            )}
          </div>
          {errors.form && (
            <p className="field-error" role="alert">
              {errors.form}
            </p>
          )}
          <button
            type="submit"
            className="primary-button"
            disabled={busy || !schema}
          >
            {busy ? (
              <>
                <LoaderCircle className="spin" size={17} />
                Estimating…
              </>
            ) : (
              <>
                {stale ? "Update estimate" : "Estimate rent"}
                <ArrowRight size={17} />
              </>
            )}
          </button>
          <p className="form-footnote">
            No name, phone number or exact address needed.
          </p>
        </form>
        <div className="result-stack">
          <section
            className="panel quote-panel"
            aria-live="polite"
            aria-atomic="true"
          >
            <div className="panel-heading">
              <h2>Your rent estimate</h2>
              <span>VND / month</span>
            </div>
            {stale && (
              <p className="stale-notice" role="status">
                <Info size={15} />
                Your details have changed. Select “Update estimate” to refresh
                the result.
              </p>
            )}
            {estimate && submitted ? (
              <>
                <div className="quote-context">
                  {categoryName(submitted.category)} · {submitted.district} ·{" "}
                  {submitted.area} m²
                  <br />
                  {bedroomName(submitted.bedrooms)} ·{" "}
                  {schema?.furnishing.find(
                    (f) => f.value === submitted.furnishing,
                  )?.label || submitted.furnishing}
                  {(submitted.ward_key !== "Unknown" ||
                    submitted.project_id !== "Unknown" ||
                    submitted.bathrooms !== "") && (
                    <>
                      <br />
                      {[
                        schema?.property_options?.wards?.find(
                          (w) => w.value === submitted.ward_key,
                        )?.label,
                        schema?.property_options?.projects?.find(
                          (p) => p.value === submitted.project_id,
                        )?.label,
                        submitted.bathrooms !== ""
                          ? bathroomName(submitted.bathrooms)
                          : undefined,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </>
                  )}
                  <br />
                  Valuation date:{" "}
                  <time dateTime={estimate.valuation_date}>
                    {calendarDate(estimate.valuation_date)}
                  </time>{" "}
                  (Hanoi time)
                </div>
                <div className="price" data-testid="quote-price">
                  {money(estimate.prediction_vnd_month)}
                  <span>million VND / month</span>
                </div>
                <div className="quote-metrics">
                  <div>
                    <span>Average validation error</span>
                    <strong>
                      {money(estimate.historical_error.mae_vnd)} million VND
                    </strong>
                  </div>
                  <div>
                    <span>
                      {estimate.historical_error.evaluation_kind ===
                      "frozen_benchmark"
                        ? "Saved benchmark"
                        : "Chronological validation"}
                    </span>
                    <strong>
                      {count(estimate.historical_error.n)} listings
                    </strong>
                  </div>
                </div>
                <p className="quote-explanation">
                  {estimate.historical_error.note} Actual rents also depend on
                  the exact location, condition and service charges.
                </p>
                {estimate.warnings.length > 0 && (
                  <ul className="warnings">
                    {estimate.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
                <div className="version-note">
                  Model <code>{estimate.model_version.slice(0, 8)}</code> ·
                  Using: {estimate.used_features.join(", ") || "overall median"}
                </div>
              </>
            ) : (
              <>
                <p className="empty-title">Start with a location and area.</p>
                <p className="quote-explanation">
                  Enter your property details to get an estimate. Leave optional
                  information as “Not specified” if you are unsure.
                </p>
                <div className="quote-metrics">
                  <div>
                    <span>Property types</span>
                    <strong>Apartments & rooms</strong>
                  </div>
                  <div>
                    <span>Currency & period</span>
                    <strong>VND / month</strong>
                  </div>
                </div>
                <p className="quote-explanation">
                  Estimates reflect advertised rents, not signed tenancy
                  agreements.
                </p>
              </>
            )}
          </section>
          {estimate &&
            submitted &&
            estimate.support.category_comparison.length > 0 && (
              <section className="panel nearby-panel">
                <div className="panel-heading">
                  <h2>Similar-size listings</h2>
                  <span>{submitted.district}</span>
                </div>
                <p className="section-note">
                  In the training data: {submitted.area} m² ±{" "}
                  {estimate.support.area_tolerance_m2} m².
                </p>
                <div className="nearby-head">
                  <span>Property type</span>
                  <span>Listings</span>
                  <span>Median asking rent</span>
                </div>
                {estimate.support.category_comparison.map((c) => (
                  <div className="nearby-row" key={c.category}>
                    <span>{categoryName(c.category)}</span>
                    <span className="num">{count(c.n)}</span>
                    <strong className="num">
                      {c.median_vnd === null
                        ? "Too few listings"
                        : `${money(c.median_vnd)} million VND`}
                    </strong>
                  </div>
                ))}
                <p className="section-note">
                  These figures do not control for furnishing, layout or
                  condition. Room listings can include serviced apartments, so
                  the two price ranges may overlap.
                </p>
              </section>
            )}
          <section className="panel layout-panel">
            <div className="panel-heading">
              <h2>What counts as a bedroom?</h2>
              <button className="text-link" onClick={onModel} type="button">
                About the model <ArrowUpRight size={14} />
              </button>
            </div>
            <LayoutPreview bedrooms={draft.bedrooms} invalid={invalidLayout} />
            <p className="section-note">
              {bedroomUsed
                ? "The model uses separate bedrooms when provided. An unspecified count stays missing; it is not replaced with zero."
                : sparseBedrooms
                  ? "Bedroom coverage is too low for this property type. Entering a count will not change its predicted rent."
                  : "This model does not use bedroom counts for this property type. Entering one will not change its predicted rent."}
            </p>
            <details>
              <summary>Area and bedroom limits</summary>
              <p>
                The app reserves at least{" "}
                {schema?.layout_policy.shared_area_m2 || 8} m² for shared space
                and {schema?.layout_policy.area_per_separate_bedroom_m2 || 10}{" "}
                m² per separate bedroom. This is an input plausibility check,
                not a building standard or verified floor plan.
              </p>
            </details>
          </section>
        </div>
      </div>
    </>
  );
}
