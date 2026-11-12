import {
  ArrowRight,
  Info,
  LoaderCircle,
  ArrowUpRight,
  ChevronDown,
} from "lucide-react";
import type { Schema, Model, Market } from "../types";
import { useEstimate } from "../useEstimate";
import { money, count } from "../format";
import LayoutPreview from "./LayoutPreview";

const categoryName = (value: string) =>
  value === "can_ho_chung_cu" ? "Căn hộ / chung cư" : "Phòng trọ";
const bedroomName = (value: string) =>
  value === ""
    ? "Chưa rõ phòng ngủ riêng"
    : value === "0"
      ? "Studio · 0 phòng ngủ riêng"
      : `${value} phòng ngủ riêng`;

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
  } = useEstimate(schema);
  const fields = model?.category_feature_schema[draft.category] || [];
  const bedroomUsed = fields.includes("bedrooms_analysis");
  const sparseBedrooms =
    model?.feature_schema.includes("bedrooms_analysis") && !bedroomUsed;
  return (
    <>
      <div className="screen-heading">
        <div>
          <h1>Ước tính giá thuê</h1>
          <p>Căn hộ và phòng trọ tại Hà Nội, theo giá chào trong tin đăng.</p>
        </div>
        <span className="scope-stamp">
          {market ? count(market.eligible_rows) : "—"} tin trong tập giá
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
            <h2>Thông tin chỗ ở</h2>
            <span>* Bắt buộc</span>
          </div>
          <fieldset className="category-field">
            <legend>Loại hình *</legend>
            <div className="category-options">
              {(
                schema?.categories || [
                  { value: "can_ho_chung_cu", label: "Căn hộ / chung cư" },
                  { value: "nha_tro", label: "Phòng trọ" },
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
          <div className="field">
            <label htmlFor="district">Quận / huyện *</label>
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
                <option value="">Chọn khu vực</option>
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
            <label htmlFor="area">Diện tích sử dụng *</label>
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
              Diện tích của riêng căn hộ hoặc phòng cho thuê.
            </p>
            {errors.area_m2 && (
              <p id="area-error" className="field-error">
                {errors.area_m2}
              </p>
            )}
          </div>
          <div className="field">
            <label htmlFor="bedrooms">
              Phòng ngủ riêng <span className="optional-label">Tuỳ chọn</span>
            </label>
            <div className="select-wrap">
              <select
                id="bedrooms"
                value={draft.bedrooms}
                onChange={(e) => update("bedrooms", e.target.value)}
                aria-invalid={invalidLayout || !!errors.bedrooms}
                aria-describedby="bedrooms-help bedrooms-error"
              >
                <option value="">Chưa rõ</option>
                <option value="0">0 — Studio / không ngăn phòng ngủ</option>
                {Array.from({ length: maximum }, (_, i) => (
                  <option key={i + 1} value={String(i + 1)}>
                    {i + 1} phòng ngủ riêng
                  </option>
                ))}
                {invalidLayout && (
                  <option value={draft.bedrooms} disabled>
                    {draft.bedrooms} phòng — không phù hợp diện tích
                  </option>
                )}
              </select>
              <ChevronDown size={15} />
            </div>
            <p id="bedrooms-help" className="field-help">
              Phòng khép kín có giường, bếp, WC nhưng không ngăn phòng ngủ: chọn
              0.
            </p>
            {(invalidLayout || errors.bedrooms) && (
              <p id="bedrooms-error" role="alert" className="field-error">
                {errors.bedrooms ||
                  `Với ${draft.area} m², tối đa ${maximum} phòng ngủ riêng theo giới hạn của ứng dụng.`}
              </p>
            )}
          </div>
          <div className="field">
            <label htmlFor="furnishing">
              Nội thất <span className="optional-label">Tuỳ chọn</span>
            </label>
            <div className="select-wrap">
              <select
                id="furnishing"
                value={draft.furnishing}
                onChange={(e) => update("furnishing", e.target.value)}
              >
                {(
                  schema?.furnishing || [{ value: "Unknown", label: "Chưa rõ" }]
                ).map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
              <ChevronDown size={15} />
            </div>
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
                Đang ước tính…
              </>
            ) : (
              <>
                {stale ? "Ước tính lại" : "Xem giá thuê tham khảo"}
                <ArrowRight size={17} />
              </>
            )}
          </button>
          <p className="form-footnote">
            Không yêu cầu tên, số điện thoại hoặc địa chỉ cụ thể.
          </p>
        </form>
        <div className="result-stack">
          <section
            className="panel quote-panel"
            aria-live="polite"
            aria-atomic="true"
          >
            <div className="panel-heading">
              <h2>Giá chào thuê tham khảo</h2>
              <span>VND / tháng</span>
            </div>
            {stale && (
              <p className="stale-notice" role="status">
                <Info size={15} />
                Thông tin đã thay đổi. Bấm “Ước tính lại” để cập nhật giá.
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
                </div>
                <div className="price" data-testid="quote-price">
                  {money(estimate.prediction_vnd_month)}
                  <span>triệu đồng / tháng</span>
                </div>
                <div className="quote-metrics">
                  <div>
                    <span>Sai số trung bình của nhóm</span>
                    <strong>
                      {money(estimate.historical_error.mae_vnd)} triệu
                    </strong>
                  </div>
                  <div>
                    <span>Benchmark đã lưu</span>
                    <strong>{count(estimate.historical_error.n)} tin</strong>
                  </div>
                </div>
                <p className="quote-explanation">
                  Sai số lịch sử không phải khoảng tin cậy cho căn này. Giá thực
                  tế còn phụ thuộc vị trí cụ thể, chất lượng và phí dịch vụ.
                </p>
                {estimate.warnings.length > 0 && (
                  <ul className="warnings">
                    {estimate.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
                <div className="version-note">
                  Mô hình <code>{estimate.model_version.slice(0, 8)}</code> ·
                  Đang dùng:{" "}
                  {estimate.used_features.join(", ") || "trung vị toàn tập"}
                </div>
              </>
            ) : (
              <>
                <p className="empty-title">Thêm thông tin để xem giá.</p>
                <p className="quote-explanation">
                  Chọn khu vực và diện tích bên cạnh. Phòng ngủ riêng và nội
                  thất có thể để “Chưa rõ”.
                </p>
                <div className="quote-metrics">
                  <div>
                    <span>Đang hỗ trợ</span>
                    <strong>Căn hộ & phòng trọ</strong>
                  </div>
                  <div>
                    <span>Đơn vị dự đoán</span>
                    <strong>VND / tháng</strong>
                  </div>
                </div>
                <p className="quote-explanation">
                  Đây là giá chào trong mẫu tin đăng, chưa phải giá giao dịch đã
                  ký hợp đồng.
                </p>
              </>
            )}
          </section>
          {estimate &&
            submitted &&
            estimate.support.category_comparison.length > 0 && (
              <section className="panel nearby-panel">
                <div className="panel-heading">
                  <h2>Tin gần diện tích này</h2>
                  <span>{submitted.district}</span>
                </div>
                <p className="section-note">
                  Trong dữ liệu huấn luyện, {submitted.area} m² ±{" "}
                  {estimate.support.area_tolerance_m2} m².
                </p>
                <div className="nearby-head">
                  <span>Loại hình</span>
                  <span>Số tin</span>
                  <span>Giá chào trung vị</span>
                </div>
                {estimate.support.category_comparison.map((c) => (
                  <div className="nearby-row" key={c.category}>
                    <span>{categoryName(c.category)}</span>
                    <span className="num">{count(c.n)}</span>
                    <strong className="num">
                      {c.median_vnd === null
                        ? "Chưa đủ mẫu"
                        : `${money(c.median_vnd)} triệu`}
                    </strong>
                  </div>
                ))}
                <p className="section-note">
                  Chưa khống chế nội thất, bố trí và chất lượng. Phòng trọ trên
                  nguồn có thể gồm căn hộ dịch vụ; giá hai loại có thể chồng
                  lấn.
                </p>
              </section>
            )}
          <section className="panel layout-panel">
            <div className="panel-heading">
              <h2>Hiểu đúng bố trí</h2>
              <button className="text-link" onClick={onModel} type="button">
                Về mô hình <ArrowUpRight size={14} />
              </button>
            </div>
            <LayoutPreview bedrooms={draft.bedrooms} invalid={invalidLayout} />
            <p className="section-note">
              {bedroomUsed
                ? "Model dùng số phòng ngủ riêng khi bạn cung cấp. Chưa rõ được xử lý như dữ liệu thiếu, không thay bằng 0."
                : sparseBedrooms
                  ? "Model của loại căn này chưa dùng số phòng ngủ riêng vì độ phủ dữ liệu còn thấp; nhập thêm sẽ không tự cộng hoặc trừ giá."
                  : "Phiên bản của loại căn này không chọn số phòng ngủ riêng để dự đoán; nhập thêm sẽ không tự cộng hoặc trừ giá."}
            </p>
            <details>
              <summary>Giới hạn diện tích và phòng ngủ</summary>
              <p>
                Ứng dụng dành tối thiểu{" "}
                {schema?.layout_policy.shared_area_m2 || 8} m² cho không gian
                chung và{" "}
                {schema?.layout_policy.area_per_separate_bedroom_m2 || 10} m²
                cho mỗi phòng ngủ riêng. Đây là quy tắc kiểm tra tổ hợp đầu vào,
                không phải quy chuẩn xây dựng hay bản xác minh mặt bằng.
              </p>
            </details>
          </section>
        </div>
      </div>
    </>
  );
}
