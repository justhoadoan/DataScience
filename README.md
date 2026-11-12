# Hanoi Rent Insight

Web ước lượng **giá chào thuê căn hộ và phòng trọ tại Hà Nội**, gồm React frontend, FastAPI backend và pipeline MLOps chạy định kỳ bằng GitHub Actions. Phạm vi không có nhà riêng hoặc giá bán.

Sản phẩm giúp người thuê có mức giá tham khảo để so sánh tin đăng và chuẩn bị ngân sách; người cho thuê có thêm cơ sở tham khảo khi đặt giá. Giá thực tế còn phụ thuộc chất lượng căn, vị trí cụ thể, phí dịch vụ và thương lượng. Xem [đề xuất đề tài và bài toán sản phẩm](docs/PRODUCT_PROPOSAL.md).

## Chạy web local

Cần Python 3.12, npm và kết nối mạng ở lần cài đặt đầu tiên. Frontend dùng Node.js >=22.12; script tự dùng Node 22 qua `npx` nếu máy đang có bản cũ.

```bash
./scripts/run_local.sh
```

Mở **http://127.0.0.1:8000**. API docs: **http://127.0.0.1:8000/docs**. Script cài dependency theo lockfile, build frontend và phục vụ model đã qua gate; không crawl hoặc train lại khi khởi động nếu đã có registry.

Ảnh demo đã kiểm tra: [desktop](docs/screenshots/estimator-desktop.png), [mobile](docs/screenshots/estimator-mobile.png), [thị trường](docs/screenshots/market-desktop.png), [mô hình](docs/screenshots/model-desktop.png).

Cài và chạy từng bước:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m hanoi_rentals.cli serve
```

Với Docker đã có daemon:

```bash
docker compose up --build
```

## Cấu trúc duy nhất đang dùng

```text
src/hanoi_rentals/
  ingestion/          # nguồn, parser, chuẩn hoá, crawl theo khoảng ngày
  eda_audit.py        # đơn vị giá, chất lượng, review, nhóm trùng
  eda_reporting.py    # EDA và biểu đồ
  modeling.py         # grouped CV, baseline, chọn model, benchmark cố định
  modeling_reporting.py
  registry.py         # phiên bản model và điều kiện thay champion
  layout.py           # nghĩa studio/phòng ngủ riêng và heuristic layout
  behavior.py         # kiểm tra hành vi giá theo diện tích/phòng ngủ
  pipeline.py         # crawl -> audit -> EDA -> train -> gate
  api.py              # API phục vụ champion
  cli.py              # entry point duy nhất
frontend/             # React + TypeScript + Vite
config/promotion.json # các ngưỡng gate được công khai
.github/workflows/    # CI, monthly, deploy
artifacts/            # registry và các model đã đánh giá
reports/              # báo cáo ứng viên mới nhất
notebooks/            # walkthrough đọc kết quả, không điều khiển pipeline
scripts/              # chạy local, state, smoke test
```

Các bản thử nghiệm, pipeline trùng và snapshot có nhà riêng đã được chuyển khỏi project. Bản backup trước refactor nằm tại `/home/gyga/Project/Personal/_archives/hanoi-rentals-before-refactor-20261030-223849.tar.gz` trên máy này.

## Dữ liệu và cách đánh giá

[Data card](docs/DATA_CARD.md) ghi số liệu hiện tại, phạm vi tháng 10, dữ liệu thiếu và giới hạn crawl. [EDA report](reports/eda_report.md) và [modeling report](reports/modeling_report.md) được sinh trực tiếp từ package.

- Dữ liệu là tin chào thuê, chưa được xác minh là giao dịch hay bất động sản duy nhất.
- Chỉ append ID mới; các trường lịch sử và ngữ cảnh review cũ được giữ nguyên. Raw response được lưu ở `data/raw/` và không commit lên Git.
- `data/benchmark/ids.csv` khóa 432 ID kiểm tra. ID benchmark và các peer cùng nhóm trùng không được đưa vào development/CV.
- Chọn cấu hình bằng grouped CV trên development. Benchmark chỉ dùng đánh giá cuối và kiểm tra thay model; nó đã được xem và tái dùng, nên không gọi là tập external/unseen.
- `reports/` thuộc ứng viên vừa chạy. Web đọc champion từ `artifacts/registry.json`; một ứng viên bị từ chối không thay model đang được phục vụ.

## Các lệnh pipeline

Chạy từ thư mục project; thêm `--root /duong/dan` **trước** tên subcommand nếu cần.

```bash
# Crawl cả phần đầu tháng đang còn truy cập được; không crawl nhà riêng.
.venv/bin/python -m hanoi_rentals.cli crawl --since 2026-10-01 --until 2026-10-30

# Audit + EDA từ snapshot hiện tại.
.venv/bin/python -m hanoi_rentals.cli eda

# Train/evaluate/gate trên snapshot đã thu thập, không tự crawl.
.venv/bin/python -m hanoi_rentals.cli train

# Luồng định kỳ: crawl, audit, EDA, train, quyết định champion.
.venv/bin/python -m hanoi_rentals.cli refresh --since 2026-10-01 --until 2026-10-30
```

Crawl thiếu nguồn, gặp 429 hoặc chưa tới ranh giới ngày được ghi trong `reports/crawl_latest.json`. Trong luồng `refresh`, các trường hợp này chặn tự động promotion. `train` là thao tác chủ động trên snapshot có sẵn; việc này không chứng nhận snapshot bao phủ toàn thị trường.

## Web và API

Bắt buộc: **loại căn**, **quận/huyện**, **diện tích sử dụng**. Tuỳ chọn: **số phòng ngủ**, **nội thất**. Trường tuỳ chọn chỉ ảnh hưởng dự đoán khi phiên bản model có sử dụng nó.

“Phòng ngủ” là **phòng ngủ riêng**: studio/phòng khép kín không ngăn phòng ngủ dùng `0`; chưa rõ thì để trống. Ứng dụng dùng heuristic `8 + 10 × phòng ngủ riêng ≤ diện tích m²`, giới hạn căn hộ tối đa 6 và phòng trọ tối đa 2; đây là chính sách tính hợp lý đầu vào, không phải quy chuẩn xây dựng. API công bố cùng policy cho form, rồi kiểm tra lại ở backend.

Ứng viên phục vụ dùng mô hình đơn điệu riêng theo category: giữ các đầu vào khác cố định, tăng diện tích hoặc số phòng ngủ riêng đã biết trong miền hợp lệ không làm giá giảm. Nếu coverage phòng ngủ đáng tin trong training của một category dưới 35%, feature đó bị bỏ và API công khai các feature thực sự dùng. Ridge/Random Forest không ràng buộc còn được giữ trong báo cáo chẩn đoán. Không ép căn hộ luôn đắt hơn phòng trọ vì các nhãn nguồn có phân khúc chồng lấn. Xem [giải thích hành vi model](docs/MODEL_BEHAVIOR.md) và [review giao diện theo hai skill thiết kế](docs/UI_REDESIGN_REVIEW.md).

| Endpoint | Mục đích |
| --- | --- |
| `GET /api/health` | Readiness và phiên bản thực sự đang phục vụ; 503 nếu model chưa sẵn sàng |
| `GET /api/schema` | Loại căn, quận/huyện và lựa chọn hợp lệ |
| `POST /api/predict` | Ước lượng VND/tháng, cảnh báo và sai số lịch sử theo nhóm |
| `GET /api/model` | Model, feature, benchmark và ngày đánh giá |
| `GET /api/market` | Thống kê mẫu theo loại căn/quận; không có thông tin người đăng |
| `GET /metrics` | Bộ đếm request và tổng thời gian xử lý |

```bash
curl http://127.0.0.1:8000/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"category":"can_ho_chung_cu","district":"Cầu Giấy","area_m2":60,"bedrooms":2,"furnishing":"Furnished"}'
```

UI hiển thị sai số đã đo trên benchmark, không tạo khoảng tin cậy giả cho từng căn. Thống kê quận là số liệu mẫu chưa khống chế diện tích/nội thất. Số tin hỗ trợ trong training và cảnh báo vùng dữ liệu thưa giúp tránh hiểu nhầm một dự đoán cục bộ là giá thị trường đã được xác minh.

## GitHub Actions và triển khai

Chưa có VPS/tên miền: hiện dùng local, chưa bật publish/deploy trên tài khoản GitHub.

- `ci.yml`: test Python, build frontend, browser E2E, build Docker và smoke test model thực.
- `monthly.yml`: **00:35 ngày 1 theo giờ Việt Nam**, crawl tháng vừa kết thúc để bao gồm toàn bộ ngày cuối tháng. Có manual dispatch để backfill.
- `deploy.yml`: đóng gói đúng champion đã đánh giá vào Docker, push GHCR và tuỳ cấu hình mới deploy qua SSH, kiểm tra health rồi rollback khi lỗi.

State được lưu thành GitHub Release assets có checksum và phiên bản theo run; lần chạy sau restore trước khi crawl. Nếu model mới không vượt gate, dữ liệu vẫn được lưu và champion cũ được giữ. GitHub cron có thể trễ và cần workflow trên default branch. Xem [hướng dẫn triển khai](docs/DEPLOYMENT.md), [kiến trúc](docs/ARCHITECTURE.md) và [đối chiếu tài liệu MLOps](docs/MLOPS_REFERENCE_NOTES.md).

## Kiểm tra

```bash
.venv/bin/python -m pytest -q
cd frontend
npm run build
npx playwright install chromium
npx playwright test
```

Browser test khởi động backend để kiểm tra form, dự đoán thật, các tab và layout mobile. Nếu cần trình duyệt có sẵn, đặt `CHROME_PATH`; nếu Python nằm trong venv ngoài `PATH`, đặt `PYTHON_BIN` thành đường dẫn tuyệt đối tới `.venv/bin/python`.

## Phân công nhóm 5 người

Đọc [phân công nhóm và liên kết đến 5 file thuyết trình riêng](docs/TEAM_PRESENTATION_GUIDE.md): (1) thu thập, (2) làm sạch/kiểm định, (3) EDA/đặc trưng, (4) model/đánh giá, (5) frontend + backend + MLOps. Mỗi file có đầu ra, code cần đọc, kiến thức, kịch bản và câu hỏi phản biện.
