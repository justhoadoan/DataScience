# Chạy local và bật GitHub Actions khi có máy chủ

Hiện chưa có VPS/tên miền theo lựa chọn của nhóm. Repo đã có code local, Docker và workflows; chưa push, cấu hình secrets hoặc bật deploy trên tài khoản GitHub trong phiên làm việc này.

Kiểm tra local ngày 30/10/2026: 42 bài test Python, một luồng browser E2E trên desktop/mobile, HTTP smoke, state roundtrip và actionlint đều đạt. Docker Compose config hợp lệ; build/chạy container chưa được xác minh do Docker Desktop daemon đang tắt. Xem `reports/verification_2026-10-30.json` để phân biệt kiểm tra đã chạy với workflow mới được chuẩn bị.

## 1. Demo local

```bash
./scripts/run_local.sh
```

Mở `http://127.0.0.1:8000`. Script dùng Node 22 qua npx khi Node hiện tại quá cũ. Cần npm và Python 3.12. Có thể đặt `PORT=8002` nếu port 8000 đang bận.

Để sửa frontend mà không build lại sau mỗi thay đổi:

```bash
# Terminal 1, từ gốc repo
.venv/bin/python -m hanoi_rentals.cli serve

# Terminal 2
cd frontend
npm run dev
```

Vite dev proxy gửi `/api` về backend port 8000. Production build được FastAPI phục vụ cùng origin nên không cần mở CORS cho mọi website.

Nếu Docker Engine đang chạy:

```bash
docker compose up --build
```

Mỗi lần startup phục vụ champion đã lưu; không tự retrain. Muốn cập nhật có chủ đích, dùng `train` hoặc `refresh` rồi khởi động lại service/container.

## 2. Đưa code lên GitHub

Kiểm tra diff và commit source, lockfiles, benchmark IDs, snapshot canonical và bundle champion ban đầu. `data/raw/`, `.venv`, `.work`, secrets và `node_modules` đã được ignore. Các file Markdown được version bình thường.

Workflow schedule chỉ chạy khi file có trên **default branch**. Repo hiện có lịch sử branch riêng; resolve divergence và review trước khi merge. Không chạy `git push --force` để bỏ qua lịch sử nhóm.

Trong Settings → Actions → General, bật quyền cần thiết cho workflows. Workflow monthly tự khai báo `contents: write` để lưu release state; workflow publish khai báo `packages: write`. Không cần tạo PAT để ghi release từ Actions vì đã có `GITHUB_TOKEN`.

## 3. Các workflow

| Workflow | Trigger và kết quả |
| --- | --- |
| `ci.yml` | Push/PR: test Python, build frontend, browser E2E, build Docker và test HTTP thật |
| `monthly.yml` | 00:35 ngày 1 giờ Việt Nam: crawl tháng vừa kết thúc, EDA, train, gate, lưu state/report |
| `deploy.yml` | Push main, manual hoặc monthly gọi lại: build champion, smoke, push GHCR; SSH chỉ khi nhóm bật |

Giờ 00:35 ngày 1 được chọn để đã qua toàn bộ ngày cuối tháng. Lịch không bảo đảm đúng từng phút. Ví dụ đợt 01/11 xử lý `2026-10-01` đến `2026-10-31`.

Để backfill thủ công trong Actions, chọn **Monthly data and model evaluation → Run workflow** rồi nhập `since=2026-10-01`, `until=2026-10-30` hoặc ngày đã qua khác. `until` tương lai bị từ chối.

Nếu chỉ có local, hai repository variables dưới đây để trống/false. Monthly vẫn có thể lưu dữ liệu và quyết định model khi được bật trên default branch; image và server không bị tác động.

| Repository variable | Ý nghĩa |
| --- | --- |
| `ENABLE_IMAGE_PUBLISH=true` | Cho phép build/push GHCR sau kiểm tra |
| `ENABLE_DEPLOY=true` | Cho phép bước SSH ra VPS đã cấu hình |
| `DEPLOY_URL=https://rent.example.com` | Tuỳ chọn: health check từ bên ngoài và rollback khi lỗi |

Không bật `ENABLE_DEPLOY` khi chưa chuẩn bị máy chủ. Không có biến nào tự mua VPS, cấp DNS hay tạo máy chủ.

## 4. State và ứng viên bị từ chối

Mỗi runner tải `state.tar.gz` và checksum từ release `rental-state`, xác minh rồi restore. Candidate mới không đạt gate vẫn được ghi report và lưu dữ liệu mới; champion tiếp tục là phiên bản cũ. Báo cáo candidate và dữ liệu phục vụ web có thể khác nhau — xem version qua `/api/health`.

Release `rental-state-<runid>-<attempt>` lưu state phiên bản và `reports.tar.gz`. Pointer `rental-state` chỉ giúp tìm bản mới nhất, không thay thế lịch sử. GitHub workflow artifacts giữ report 90 ngày; release state tồn tại cho tới khi người quản lý xoá.

Với dữ liệu/model lớn hơn, thay GitHub Release assets bằng S3/R2/MinIO + registry tương ứng; project hiện chưa cần hạ tầng này. Không dùng cache Actions làm nguồn dữ liệu duy nhất vì cache có thể hết hạn hoặc bị evict.

## 5. Chuẩn bị VPS sau này

Cần máy Linux có Docker Engine + Compose v2, SSH user được phép chạy Docker, cổng 80/443 mở, domain trỏ tới IP. Nên bắt đầu với 2 vCPU và 2–4 GB RAM rồi đo mức dùng thực tế; đây là cấu hình khởi đầu tham khảo, chưa được benchmark trên VPS trong phiên này.

Trong home của user deploy, chuẩn bị:

```bash
mkdir -p ~/hanoi-rentals
cd ~/hanoi-rentals
printf 'DOMAIN=rent.example.com\n' > .env
```

Workflow copy `compose.production.yml`, `Caddyfile` và `remote-deploy.sh` vào thư mục này. Caddy tự xử lý HTTPS khi domain và cổng đã sẵn sàng. API chỉ expose trong network Docker, người dùng đi qua Caddy.

Tạo environment `production` trong GitHub để quản lý secrets và optional review rules. Thiết lập:

| Secret | Nội dung |
| --- | --- |
| `DEPLOY_HOST` | Host/IP VPS |
| `DEPLOY_USER` | SSH user |
| `DEPLOY_SSH_KEY` | Private key dành riêng cho deploy |
| `DEPLOY_KNOWN_HOSTS` | Dòng host key đã xác minh với máy chủ |

Không commit key hoặc `.env`. Host key cần lấy/kiểm tra qua kênh quản trị máy chủ; không tắt `StrictHostKeyChecking` để làm deployment đi qua.

Workflow dùng SSH agent cho key và truyền token GHCR qua stdin; token ngắn hạn được logout sau deploy. Image được tham chiếu bằng digest `ghcr.io/...@sha256:...`, tránh việc tag bị đổi âm thầm.

## 6. Rollout và rollback

`remote-deploy.sh` lưu image cũ, pull digest mới và chạy `docker compose up --wait`. HEALTHCHECK gọi `/api/health`, do đó model chưa load được không được xem là sẵn sàng. Khi pull/start/readiness lỗi, script phục hồi image cũ. Nếu có `DEPLOY_URL` và public health check lỗi, workflow gọi rollback.

Rollback thủ công trên máy chủ:

```bash
cd ~/hanoi-rentals
bash remote-deploy.sh --rollback
```

Cơ chế này có thể có gián đoạn ngắn khi container được thay; chưa phải blue/green không downtime. Deploy thành công phải được xác nhận bằng URL thực và model version, không chỉ bằng một bước Docker push màu xanh.

## 7. Vận hành và giới hạn hiện tại

- `/api/health`: model đang phục vụ và readiness. `/metrics`: request count/status và tổng duration; có thể scrape bằng hệ thống monitoring sau này.
- `reports/crawl_latest.json`: nguồn nào thiếu, oldest date, số trang, HTTP errors. Không bỏ qua 429 để tuyên bố đủ tháng.
- `reports/pipeline_latest.json`: candidate, champion, lý do gate, data quality và drift.
- Cập nhật dependency ML cần kiểm tra tương thích artifact; không chỉ đổi version rồi coi model cũ vẫn tái lập.
- Benchmark tái dùng cần quản lý thay/version theo quy trình, và kiểm tra thêm cohort thời gian chưa xem.
- Local/CI tests không chứng minh website đã online. Chưa có production host thì không có production URL hoặc monthly schedule đã được xác nhận chạy thật.

Tham khảo chính thức: [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/), [Vite prerequisites](https://vite.dev/guide/).
