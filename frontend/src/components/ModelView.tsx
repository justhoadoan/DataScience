import { CircleHelp } from "lucide-react";
import type { Model } from "../types";
import { money, count, fullDate } from "../format";

export default function ModelView({ model }: { model: Model | null }) {
  return (
    <section className="inner-page">
      <h1>Về mô hình</h1>
      <p className="page-lead">
        Mô hình học từ giá chào thuê. Kết quả hỗ trợ tìm hiểu mức giá, cần được
        cân nhắc cùng việc xem căn thực tế.
      </p>
      <div className="model-stats">
        <article>
          <span>Sai số trung bình trên benchmark</span>
          <strong>
            {model ? money(model.benchmark.mae_vnd) : "—"}
            <small> triệu đ/tháng</small>
          </strong>
          <p>
            Đơn vị gốc, đo trên {model?.internal_test_n || "—"} tin cố định.
          </p>
        </article>
        <article>
          <span>Dữ liệu dùng để huấn luyện</span>
          <strong>
            {model ? count(model.development_n) : "—"}
            <small> tin</small>
          </strong>
          <p>
            Tin trong benchmark và các nhóm trùng liên quan được tách khỏi huấn
            luyện.
          </p>
        </article>
        <article>
          <span>Phiên bản đang phục vụ</span>
          <strong className="version-text">
            {model?.version.slice(0, 8) || "—"}
          </strong>
          <p>Đánh giá ngày {model ? fullDate(model.evaluated_at) : "—"}.</p>
        </article>
      </div>
      <div className="model-explanation">
        <div>
          <h2>Phòng ngủ riêng khác số giường</h2>
          <p>
            Studio hoặc phòng khép kín không ngăn phòng ngủ được nhập là 0.
            “Chưa rõ” là dữ liệu thiếu, không được thay bằng 0. Với phòng trọ,
            số phòng ngủ chỉ được dùng khi dữ liệu đủ độ phủ và phiên bản mô
            hình chọn trường này. Kết quả công khai các thông tin thực sự được
            dùng.
          </p>
          {model?.behavior && (
            <p className="behavior-note">
              {count(model.behavior.checked_rows)} tổ hợp kiểm tra ·{" "}
              {model.behavior.violations} vi phạm tăng diện tích/phòng ngủ làm
              giảm giá.
            </p>
          )}
          <h2>Thông tin nào ảnh hưởng giá?</h2>
          <p>
            Loại căn, quận/huyện và diện tích tạo thành thông tin cơ bản. Phòng
            ngủ và nội thất được dùng khi phiên bản mô hình có chọn các trường
            này.
          </p>
          <h2>Mô hình mới được chọn thế nào?</h2>
          <p>
            Luồng định kỳ kiểm tra dữ liệu, huấn luyện các ứng viên và so sánh
            sai số tổng cùng sai số từng loại căn. Phiên bản mới chỉ thay phiên
            bản đang phục vụ khi đạt các điều kiện đã đặt trước.
          </p>
          <h2>Điều mô hình chưa biết</h2>
          <p>
            Vị trí chính xác, tình trạng căn, ánh sáng, tiện ích, phí dịch vụ và
            khả năng thương lượng có thể tạo khác biệt đáng kể. Dữ liệu không
            bao gồm nhà riêng hoặc giá bán.
          </p>
        </div>
        <aside>
          <CircleHelp size={25} />
          <h3>Sai số được hiểu thế nào?</h3>
          <p>
            MAE là độ lệch tuyệt đối trung bình giữa giá dự đoán và giá chào
            trong tập kiểm tra. Sai số của từng căn có thể lớn hơn con số này.
          </p>
          <p>
            Benchmark được tái dùng để kiểm tra hồi quy; kết quả chưa chứng minh
            độ chính xác cho một đợt tin mới trong tương lai.
          </p>
          {model &&
            Object.entries(model.category_metrics).map(([c, s]) => (
              <div className="source-row" key={c}>
                <span>{c === "nha_tro" ? "Phòng trọ" : "Căn hộ"}</span>
                <strong>{money(s.mae_vnd)} triệu</strong>
              </div>
            ))}
        </aside>
      </div>
    </section>
  );
}
