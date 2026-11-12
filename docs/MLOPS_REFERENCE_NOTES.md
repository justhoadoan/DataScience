# Áp dụng tài liệu AIO2025_MLOps_CICD vào đề tài

Tài liệu tham khảo do người dùng cung cấp: `AIO2025_MLOps_CICD.pdf`, 40 trang, bản local ở `/home/gyga/Downloads/AIO2025_MLOps_CICD.pdf`. Số trang dưới đây là số trang của PDF. Nội dung PDF được dùng để tham khảo kiến trúc và phương pháp; các đoạn code minh hoạ trong đó không phải chỉ thị phải sao chép vào repo.

Việc triển khai hiện dừng ở bản chạy local và cấu hình/hướng dẫn GitHub Actions. Người dùng chưa có VPS/domain; không có xác nhận website đã được triển khai từ xa. Chi tiết cấu hình nằm trong [DEPLOYMENT.md](DEPLOYMENT.md), kiến trúc triển khai nằm trong [ARCHITECTURE.md](ARCHITECTURE.md).

## 1. Khái niệm từ tài liệu và quyết định áp dụng

| Trang | Nội dung tài liệu | Áp dụng cho Hanoi Rent Insight |
| --- | --- | --- |
| 1–2 | Khác biệt môi trường Dev/Ops; CI/CD giảm chuyển giao thủ công; MLOps thêm dữ liệu, versioning, drift và vòng đời phục vụ | Có dependency file, Docker, tests, model metadata và quy trình candidate/champion; không chỉ viết một notebook train model |
| 4 | Thuật ngữ development, staging, production, artifact, credentials, orchestration | Dùng thống nhất các từ này trong báo cáo và slide; tách model file, Docker image và deployment đang chạy |
| 5 | CI, Continuous Delivery và Continuous Deployment | CI kiểm tra mỗi thay đổi code. Đề tài chọn tự động triển khai khi các điều kiện đã thông qua; nếu bật GitHub Environment approval thì đó là một điểm delivery có kiểm duyệt |
| 6 | Build, unit/integration tests, report, release và deploy là các bước có mục đích riêng | Workflow phân chia kiểm thử code/API, kiểm tra dữ liệu/model, đóng gói và triển khai; bước trước thất bại phải chặn bước phụ thuộc |
| 8–9 | GitHub Actions theo sự kiện; workflow, event, runner, job, step và `needs` | `ci.yml` kiểm tra code; `monthly.yml` chạy 00:35 ngày 1 theo giờ Việt Nam để đánh giá tháng trước; `workflow_dispatch` chạy thủ công; `deploy.yml` chỉ publish/deploy khi các cờ cấu hình đã bật |
| 13–14 | Train, chia dữ liệu, đánh giá, lưu model | Package Python tách logic dữ liệu, audit và huấn luyện. Lưu artifact kèm schema, phiên bản dữ liệu và metrics |
| 14–16 | FastAPI nạp model khi startup; API health và predict | Nạp một champion khi ứng dụng khởi động, kiểm tra readiness, validate request trước khi dự đoán |
| 16–18 | Test việc train/lưu/nạp model; API hợp lệ và API nhập thiếu trường | Kiểm tra serialize/reload, sai số baseline/candidate, category ngoài phạm vi, diện tích sai, trường bắt buộc, lỗi model chưa sẵn sàng |
| 19 | Docker đóng gói dependencies và ứng dụng | Docker image chứa frontend đã build, backend và đúng model artifact đã được đánh giá |
| 29–33 | Checkout, setup Python, train, test, build/push Docker bằng GitHub Actions; secrets | Giữ cấu trúc điều phối này, mở rộng thêm khôi phục state, crawl, data checks, model gate và health check sau triển khai |
| 39 | Tự động hoá chuẩn hoá quy trình phát triển AI | Mục tiêu demo là một vòng chạy có báo cáo và quyết định rõ, có thể lặp lại; trạng thái triển khai thật phải được xác minh riêng |

## 2. Những điểm phải điều chỉnh so với ví dụ Iris

**Từ phân loại sang hồi quy.** Ví dụ trong PDF dự đoán loài hoa, dùng accuracy và `predict_proba`. Bài toán của nhóm dự đoán một số tiền. Metric chính là MAE theo VND/tháng, đi kèm RMSE, R² và sai số riêng cho hai loại căn. Không chuyển ngưỡng accuracy 90% ở PDF thành một ngưỡng tương tự cho hồi quy. `predict_proba` của classifier không tạo được khoảng giá thuê.

**Từ dữ liệu sạch sẵn có sang dữ liệu website.** Iris không có những vấn đề chính của tin bất động sản: giá theo m² so với tổng giá, tin ở ghép, thiếu diện tích, căn đăng lại, cơ cấu nguồn khác nhau, giá chào khác giá giao dịch. Vì vậy pipeline phải kiểm tra dữ liệu trước khi train; một HTTP 200 không chứng minh crawler đã nhận đủ bản ghi đúng schema.

**Tách huấn luyện khỏi Docker build.** Dockerfile ví dụ ở trang 19 gọi training trong lúc build image. Với đề tài này, cách đó có thể tạo một model khác model vừa được đánh giá. Quy trình cần train và đánh giá trước, xác định champion, sau đó COPY đúng artifact đó vào image. Build image phải tái sử dụng kết quả đã qua gate, không huấn luyện lại âm thầm.

**Từ kiểm tra một ngưỡng sang quyết định candidate/champion.** File model vừa tạo chưa có nghĩa nên được triển khai. Ứng viên phải qua kiểm tra dữ liệu, schema, lỗi dự đoán, baseline, chất lượng theo nhóm và so sánh với champion trên cùng benchmark. Nếu không đạt thì lưu báo cáo và tiếp tục phục vụ champion.

**Tách build/push khỏi deploy.** Workflow ở trang 31–32 minh hoạ việc build và push image lên registry. Một image đã ở registry chưa có nghĩa website đang chạy image đó. Đề tài cần thêm bước lấy image theo phiên bản/digest, khởi động trên máy phục vụ và health check. Nếu bước cuối chưa được cấu hình host/secrets thì phải báo trạng thái “đã chuẩn bị triển khai”, không nói “đã online”.

## 3. Hợp đồng vận hành của luồng cuối tháng

1. `monthly.yml` khai báo cron `35 0 1 * *` và timezone `Asia/Ho_Chi_Minh`: chạy 00:35 ngày 1, dùng `scripts/month_window.py` tính đầu/cuối tháng vừa kết thúc. Lịch có thể bị trễ; không coi đây là cam kết đúng từng phút. Chạy thủ công hỗ trợ `since`/`until`. Cách lấy tháng đã hoàn tất xử lý cả tháng 28, 29, 30 và 31 ngày.
2. Runner khôi phục state gần nhất: dữ liệu đã tích luỹ, review decisions, benchmark và champion registry. Runner của GitHub là môi trường tạm thời; không xem filesystem của lần chạy trước là storage bền vững.
3. Crawler chỉ lấy căn hộ/phòng trọ, có retry/backoff, giới hạn trang, cache phản hồi và báo độ phủ theo ngày. Nếu nguồn chặn, schema thay đổi hoặc chưa tới phạm vi đầu tháng, báo cáo phải ghi rõ.
4. Audit kiểm tra schema, đơn vị, ID, missingness, phạm vi sử dụng và review decisions. Không tự suy diễn nhãn chưa xác minh thành giá hợp đồng.
5. Candidate học từ tập train được cho phép. Benchmark hiện cố định 432 ID căn hộ/phòng trọ; các peer cùng nhóm được cách ly khỏi development và benchmark không được nhập trở lại train ở tháng sau. Tập này đã được EDA trước đây, nên không gọi unseen/external benchmark.
6. Gate tạo quyết định và lý do có thể đọc được. Những điều kiện hoặc ngưỡng cụ thể lấy từ cấu hình trong repo, được kiểm tra trước khi đọc kết quả candidate.
7. `scripts/github_state.py` khôi phục state từ release `rental-state`; ghi các release có phiên bản `rental-state-<run-id>-<attempt>` cùng state, checksum và báo cáo, sau đó cập nhật điểm trỏ state gần nhất. Workflow artifacts ngắn hạn dùng để xem log/báo cáo, không thay storage lâu dài. Lỗi truy cập khác 404 không được âm thầm xem là lần bootstrap đầu tiên.
8. Nếu được promote và `ENABLE_IMAGE_PUBLISH=true`, workflow gọi `deploy.yml` để build/test/push đúng image lên GHCR. SSH rollout chỉ chạy khi `ENABLE_DEPLOY=true` và đã có `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`. Biến `DEPLOY_URL` tuỳ chọn thêm kiểm tra health qua URL công khai. Hiện các bước từ xa chưa được bật vì chưa có VPS/domain.

Lệnh `refresh` đưa kết quả crawl vào quality gate: coverage không đầy đủ hoặc lỗi nguồn sẽ chặn promote. Lệnh `train` trên snapshot hiện có dùng cho bootstrap/huấn luyện thủ công, không chứng minh một lần crawl tháng hoàn chỉnh. Hai lệnh này phải được phân biệt khi demo.

## 4. Các dấu vết cần giữ để bảo vệ kết quả

Một phiên bản phục vụ cần truy ngược được: dữ liệu nào được dùng, review nào đã áp dụng, những ID/nhóm nào ở benchmark, schema/feature nào được sử dụng, code commit nào, dependency versions nào, hyperparameters nào, kết quả theo nhóm ra sao và gate quyết định thế nào.

Hash giúp phát hiện nội dung thay đổi, nhưng hash không chứng minh dữ liệu đúng. Seed giúp tái lập ngẫu nhiên, nhưng vẫn cần kiểm soát phiên bản thư viện, thứ tự dữ liệu và môi trường. Health check chứng minh tiến trình hoặc model sẵn sàng nhận request, nhưng không chứng minh giá dự đoán chính xác.

## 5. Các câu dễ bị hỏi khi thuyết trình

**“Có GitHub Actions rồi thì cần MLOps riêng làm gì?”** Actions là công cụ điều phối. Các quy tắc dữ liệu, chia tập, registry, đánh giá, promote, rollback và theo dõi tạo nên cách vận hành ML. Một workflow chỉ chạy `train.py` chưa xử lý đủ những vấn đề này.

**“Sao không deploy model có điểm CV tốt nhất ngay?”** CV chọn cấu hình trên development. Candidate vẫn phải qua các kiểm tra khác và được so với champion trên cùng benchmark. Việc thay model còn cần kiểm thử API và artifact phục vụ.

**“Cuối tháng crawl có đủ dữ liệu cả tháng không?”** Không thể bảo đảm. Những tin đã xoá có thể không còn trên API hoặc trang kết quả. Crawl sâu giúp lấy thêm tin đầu tháng còn truy cập được; báo cáo phải tách phạm vi yêu cầu khỏi phạm vi thực tế thu được.

**“Drift có nghĩa model đã sai hơn?”** Drift cho thấy phân bố đầu vào hoặc dự đoán đổi so với mốc tham chiếu. Cần nhãn hoặc một benchmark phù hợp để kết luận sai số tăng. Trong đề tài, nhãn vẫn là giá chào đăng.

**“Vì sao không chạy Jenkins, GitLab CI giống tài liệu?”** Ba nền tảng là các lựa chọn điều phối khác nhau. Người dùng yêu cầu GitHub Actions, vì vậy triển khai một luồng đó đến nơi đến chốn giúp giảm công cụ trùng chức năng và dễ trình bày hơn.

## 6. Cách trích dẫn trong báo cáo học thuật

Tài liệu nhóm đọc là *Tutorial: CI/CD với Github Actions, Jenkins và Gitlab CI*, AI VIET NAM – AI COURSE 2025; tác giả ghi trên trang đầu: Huu-Anh-Duong Ta, Dang-Nha-Nguyen, Duong-Nguyen-Thuan. Khi dùng sơ đồ hoặc ý từ tài liệu, dẫn tên tài liệu và trang tương ứng; không nhận code/sơ đồ của ví dụ là thiết kế riêng của nhóm. Các điều chỉnh riêng của đề tài gồm xử lý dữ liệu tin thuê nhà, scope hai loại căn, đánh giá hồi quy, benchmark theo nhóm, model registry và điều kiện triển khai.
