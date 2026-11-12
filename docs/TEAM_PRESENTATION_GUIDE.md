# Phân công và tài liệu thuyết trình cho nhóm 5 người

**Báo cáo tiến độ 5 phút:** dùng [bộ 9 slide tiếng Anh](../presentations/capstone-progress/README.md), [PDF](../presentations/capstone-progress/progress-report.pdf) và [lời thoại theo thời gian](../presentations/capstone-progress/speaker-notes.md). Bộ này tập trung vào objective, learning problem, dữ liệu mẫu, pipeline dự kiến và UI nháp. Phân công chi tiết bên dưới phục vụ bài thuyết trình đầy đủ của nhóm.

Tài liệu này chia dự án thành **đúng 5 phần**, tương ứng 5 người. MLOps được gộp cùng frontend/backend ở Người 5. Kiến thức chi tiết được tách thành một file Markdown cho mỗi người; file này là mục lục và quy ước chung. Mỗi người cần trình bày được vấn đề, dữ liệu vào/ra, quyết định kỹ thuật, bằng chứng kiểm tra và giới hạn phần mình làm. Không cần đọc hết code trên slide. Các số liệu cuối cùng lấy từ báo cáo do lần chạy hiện tại sinh ra; không chép lại số liệu snapshot cũ khi dữ liệu đã đổi.

Tên đề tài và bài toán sản phẩm nằm trong [PRODUCT_PROPOSAL.md](PRODUCT_PROPOSAL.md). Cách vận dụng PDF AIO và trang tham khảo nằm trong [MLOPS_REFERENCE_NOTES.md](MLOPS_REFERENCE_NOTES.md). `README.md` ở gốc repo là nguồn chính cho lệnh cài đặt và chạy hiện tại.

**Môi trường demo hiện tại là local.** Người dùng chưa có VPS/domain, nên không trình bày SSH rollout hoặc website công khai như việc đã hoàn thành. Chạy `./scripts/run_local.sh` để khởi động sản phẩm tại cổng 8000; script hỗ trợ môi trường Node 22, có phương án `npx` khi cần. Cấu hình triển khai từ xa đã được chuẩn bị trong [DEPLOYMENT.md](DEPLOYMENT.md).

Đợt dữ liệu tháng 10 hiện có 5.836 tin, bổ sung 3.631 tin so với snapshot hai category trước đó; trong phần bổ sung có 1.135 tin đăng 01–13/10. Nhatot đã trả đến cuối tập kết quả công khai; Alonhadat trả 429 sau 40 trang căn hộ và chặn phòng trọ. Đây là coverage chưa đầy đủ của một nguồn, cần đưa vào phần giới hạn. Benchmark cố định hiện giữ 432 ID. Trước khi lên slide, đối chiếu lại [DATA_CARD.md](DATA_CARD.md), registry và báo cáo mới nhất vì các giá trị này sẽ thay đổi ở lần cập nhật tiếp theo.

Champion sau lần sửa hành vi là `ec9a7bf02b42ae3b`: MAE benchmark khoảng 1.544 triệu VND/tháng, căn hộ 2.365 triệu, phòng trọ 0.986 triệu; R² chung 0.7354. Khi so lại legacy trên cùng feature phòng ngủ đã làm sạch, MAE chung giảm khoảng 0.9514%; không dùng điểm legacy lưu trước khi audit đổi ngữ nghĩa phòng ngủ để nhận là một so sánh cùng điều kiện. Kết quả local: 52 pytest/4 Playwright E2E đạt, probe 5,292 đầu vào hợp lệ có 0 vi phạm ở candidate so với 1,719 ở legacy. Xem [MODEL_BEHAVIOR.md](MODEL_BEHAVIOR.md) và [verification report](../reports/verification_behavior.json) cho evidence và giới hạn.

## Phân công mới và tài liệu riêng

| Người | Phần sở hữu | File học và thuyết trình | Đầu ra chính | Thời lượng |
| --- | --- | --- | --- | --- |
| 1 | Thu thập dữ liệu | [01_DATA_COLLECTION.md](team/01_DATA_COLLECTION.md) | Crawler, raw cache, snapshot, coverage và lỗi nguồn | 5 phút |
| 2 | Làm sạch và kiểm định dữ liệu | [02_DATA_QUALITY.md](team/02_DATA_QUALITY.md) | Audit, quy tắc đơn vị/scope/layout, review queue, eligibility và nhóm trùng | 5 phút |
| 3 | EDA và đặc trưng | [03_EDA_FEATURES.md](team/03_EDA_FEATURES.md) | Phân tích phân bố/missingness/bias, hình và feature whitelist | 5 phút |
| 4 | Mô hình và đánh giá | [04_MODELING_EVALUATION.md](team/04_MODELING_EVALUATION.md) | Baseline, grouped CV, model, benchmark, behavior checks và tiêu chí chất lượng | 7 phút |
| 5 | Frontend + Backend + MLOps | [05_WEB_MLOPS.md](team/05_WEB_MLOPS.md) | Website, API, CI/CD, monthly pipeline, state/registry, Docker và vận hành | 10 phút, gồm demo |

Tổng gợi ý **32 phút**, khoảng **19 slide**: 3 + 3 + 3 + 4 + 6. Phần Người 5 rộng hơn nên được nhiều thời gian hơn; không chuyển mọi kiểm thử và quyết định dữ liệu/model cho một người. Người 1 mở đầu bằng bài toán, Người 5 demo và kết luận; không cần người thứ sáu hoặc phần MLOps độc lập.

## Ranh giới và bàn giao

| Từ → đến | Hợp đồng bàn giao |
| --- | --- |
| 1 → 2 | Snapshot processed + raw evidence + manifest/coverage; chưa gọi là dữ liệu đã audit |
| 2 → 3 và 4 | Analysis dataset, dictionary, eligibility, review và split_group nhất quán |
| 3 → 4 | EDA, feature plan, giới hạn/bias; không fit preprocessing trên benchmark |
| 4 → 5 | Artifact kèm preprocessing, schema/metadata, metrics, behavior probe và chính sách model |
| 5 → cả nhóm | Website chạy local, workflow gọi các module, run report, version phục vụ và trạng thái deploy thật |

Người 1 sở hữu thu thập/parsing ở adapter; Người 2 kiểm định ý nghĩa và giữ dấu vết quyết định. Người 2 sở hữu logic audit trong `eda_audit.py`, Người 3 sở hữu hình/báo cáo trong `eda_reporting.py`, dù CLI `eda` gọi cả hai. Người 4 sở hữu thuật toán và lý do của ngưỡng chất lượng; Người 5 triển khai gate/registry/workflow và API. Khi đổi policy, hai người cùng rà soát.

## Kiến thức cả nhóm cần thống nhất

- Dự đoán là **giá chào thuê VND/tháng** của căn hộ/phòng trọ tại Hà Nội.
- Nhà riêng và giá bán bất động sản nằm ngoài phạm vi.
- Mỗi dòng là một **tin đăng**, chưa xác minh là một bất động sản riêng biệt hoặc một giao dịch.
- Model tốt hơn baseline trên benchmark không đồng nghĩa dùng tốt ở mọi quận, mọi thời điểm hoặc mọi phân khúc.
- Không dùng `R² = 0,73` để nói “chính xác 73%”. Không dùng MAE làm khoảng bảo đảm cho một căn cụ thể.
- Tự động chạy pipeline khác với tự động thay model: candidate không đạt điều kiện thì champion tiếp tục được phục vụ.

## Ghép bài và demo

Luồng thuyết trình: **thu thập → audit → EDA/feature → model/evaluation → web/vận hành**. Mỗi người mở phần mình bằng đầu vào nhận từ người trước và kết thúc bằng sản phẩm bàn giao. Mỗi slide trả lời một câu hỏi, có một hình hoặc bảng bằng chứng và một kết luận; tránh đưa nguyên code lên slide.

Demo nằm trong 10 phút của Người 5: nhập thông tin, nhận giá/metadata, thử studio và input sai, mở decision/run report rồi đối chiếu champion với `/api/model`. Không live crawl dài hoặc đổi ngưỡng để ép promote. Người 1–4 chuẩn bị bằng chứng cho phần của mình và hỗ trợ trả lời theo chuyên môn.

Chốt chung trước buổi tổng duyệt: số dòng/tập giá/benchmark, MAE và RMSE theo nhóm, mốc dữ liệu, coverage từng nguồn, model version đang phục vụ và trạng thái deploy. Lấy từ báo cáo/API mới nhất, không giữ số snapshot cũ trên slide.

## Tự kiểm tra trước khi nộp

- Người 1: đối chiếu một raw response với processed, giải thích khoảng ngày, lỗi nguồn và append không trùng ID.
- Người 2: giải thích một quy tắc đơn vị/scope, studio 0 khác missing, review queue và nhóm trùng.
- Người 3: chỉ ra một bias, một missingness pattern, một feature leakage và cách kiểm tra nhạy cảm.
- Người 4: tính MAE, giải thích grouped CV/benchmark, mô hình đơn điệu và lý do chọn/reject candidate.
- Người 5: demo FE/BE, phân biệt CI/train/promote/build/push/deploy, biết state và cách giữ champion/rollback.
- Cả nhóm: nói đúng “giá chào thuê tham khảo”; không biến R² thành accuracy hoặc MAE thành khoảng bảo đảm.

## Lệnh dùng khi học và diễn tập

Chạy từ gốc repo sau khi cài package theo README. `--root` là tuỳ chọn chung nên đặt **trước** tên subcommand. Các lệnh crawl/refresh thật có gửi request ra website; dùng raw cache hoặc báo cáo đã chạy cho phần demo ngắn.

```bash
# Xem hợp đồng CLI
python -m hanoi_rentals.cli --help
python -m hanoi_rentals.cli crawl --help

# Chỉ cập nhật dữ liệu, phạm vi tháng 10 tính đến ngày minh hoạ
python -m hanoi_rentals.cli crawl \
  --since 2026-10-01 --until 2026-10-30 --max-pages 120

# Kiểm tra dữ liệu và sinh EDA từ snapshot hiện có
python -m hanoi_rentals.cli eda

# Bootstrap/huấn luyện thủ công trên snapshot hiện có; không chứng nhận coverage crawl
python -m hanoi_rentals.cli train

# Crawl rồi chạy toàn bộ pipeline trong một lệnh
python -m hanoi_rentals.cli refresh \
  --since 2026-10-01 --until 2026-10-30 --max-pages 120

# Phục vụ champion đã qua gate và frontend đã build
python -m hanoi_rentals.cli serve --host 127.0.0.1 --port 8000
```

Ngày trong ví dụ là ngày của đợt backfill tháng 10 đang xây dựng. Với một tháng khác, thay cả hai mốc phù hợp hoặc dùng mặc định CLI từ đầu tháng hiện tại đến hôm chạy. Workflow monthly chủ động truyền khoảng ngày **tháng trước đã hoàn tất**, khác mặc định CLI. `max-pages` là giới hạn hữu hạn; đạt giới hạn trước khi chạm phạm vi cần lấy phải được báo là coverage chưa đủ. Để demo web nhanh, dùng `./scripts/run_local.sh` thay vì tự thực hiện lại từng lệnh cài đặt/build/serve.

Các file cần mở khi trả lời về trạng thái cuối cùng:

- `reports/eda_report.md`: dữ liệu đã audit của lần chạy gần nhất.
- `reports/modeling_report.md`: kết quả candidate của lần huấn luyện gần nhất.
- `reports/pipeline_latest.json`: data quality và quyết định của lần pipeline gần nhất.
- `artifacts/registry.json`: version đang là champion và lịch sử promote/reject.
- `artifacts/models/<version>/metadata.json`: schema, metrics và dữ liệu của phiên bản đó.
- `GET /api/model`: champion thực sự đang được tiến trình API phục vụ.

Candidate mới nhất có thể bị reject. Vì vậy báo cáo huấn luyện mới nhất và model đang chạy trên web có thể là hai phiên bản khác nhau; đây là hành vi cần giải thích khi demo.
