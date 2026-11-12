# Data card — dữ liệu căn hộ và phòng trọ Hà Nội

Cập nhật theo đợt crawl ngày 30/10/2026. Dữ liệu và báo cáo đang dùng chỉ gồm căn hộ/chung cư (`can_ho_chung_cu`) và phòng trọ (`nha_tro`).

## Số lượng và phạm vi

- Bảng tích luỹ: **5,836 tin**; ID duy nhất: **5,836**.
- Tập giá sau audit: **5,739 tin**; loại khỏi tập giá: **97**.
- Ngày hiển thị trên nguồn: **2026-07-30 đến 2026-10-30**.
- Tin có ngày hiển thị tháng 10: **3,941**; trong đó ngày 01–13/10: **1,135**.
- Bổ sung trong đợt này: **3,631 tin**, gồm **1,135 tin đầu tháng**.
- Đang chờ quyết định review: **70 tin**.

| Nguồn | Loại | Số tin | Thiếu diện tích gốc |
| --- | --- | ---: | ---: |
| alonhadat | Căn hộ | 1,087 | 0.0% |
| alonhadat | Phòng trọ | 299 | 0.0% |
| nhatot | Căn hộ | 2,086 | 54.3% |
| nhatot | Phòng trọ | 2,364 | 53.1% |

## Độ phủ đầu tháng và lỗi nguồn

Nhatot đã duyệt đến hết kết quả API truy cập được cho hai loại; phản hồi có cả tin từ 01/10 và một số tin trước tháng để xác định ranh giới. Alonhadat dừng ở 40 trang căn hộ vì HTTP 429; nguồn phòng trọ cũng bị 429. Vì vậy không tuyên bố thu đủ toàn tháng ở cả hai nguồn. Đợt crawl này chốt đến 30/10 và chưa bao gồm 31/10; lịch đầu tháng sau sẽ xử lý tháng vừa hoàn tất.

Tin đã xoá, hết hạn hoặc không được API trả về không thể khôi phục chỉ bằng phân trang. Ngày hiển thị/list_time có thể phản ánh việc đẩy lại tin, không bảo đảm là lần đăng đầu tiên. Raw JSON/HTML được cache ở `data/raw/2026-10-30/` và được ignore khỏi Git; coverage nằm ở `reports/crawl_latest.json`.

## Ý nghĩa và hạn chế

- Mỗi dòng là một tin đăng; không phải giao dịch đã ký hoặc một căn đã xác minh là duy nhất.
- Các ID cũ không bị cập nhật âm thầm. Snapshot tích luỹ nhiều thời điểm, nên không đồng nghĩa toàn bộ các tin vẫn còn hoạt động.
- Missingness khác nhau rõ giữa nguồn. Thiếu diện tích không được coi là 0; nội thất Unknown không được coi là nhà trống.
- Các quận/huyện sử dụng địa chỉ theo nguồn; chưa có đối soát đầy đủ với địa giới phường/xã mới.
- Keyword flags và review CSV chưa thay thế kiểm chứng tin gốc. Tin diễn đạt lại hoặc đăng chéo nguồn có thể chưa được phát hiện trùng.
- Trước khi append, 10 dòng trong đợt crawl bị loại bởi sanity rule diện tích ≤5 m² hoặc giá trên 1 triệu VND/m²/tháng. Đây là quy tắc chuẩn hoá có thể tạo selection bias; nó khác với việc trim P1/P99 sau khi xem lỗi model.
- Mẫu thu thập thuận tiện, có ảnh hưởng quảng cáo/đẩy tin và lệch nguồn; không dùng trung vị mẫu để kết luận toàn thị trường.
- Website chỉ hiển thị aggregates, không hiển thị số điện thoại/tài khoản từ raw response.

## Snapshot dùng cho mô hình hiện tại

Version champion: `ec9a7bf02b42ae3b`. Tập giá EDA có 5,739 tin; modeling dùng 5,733 tin sau khi cách ly peer trùng benchmark. Development: 5,301; benchmark cố định: 432. Model được chọn là HistGradientBoosting có ràng buộc đơn điệu, loss `squared_error` trên target log, feature set C và học riêng theo category. Grid phục vụ gồm 8 cấu hình HGB và 4 Random Forest có ràng buộc; 8 Ridge và 16 Forest không ràng buộc được giữ để chẩn đoán.

| Nhóm benchmark | n | MAE (triệu VND/tháng) |
| --- | ---: | ---: |
| Chung | 432 | 1.544 |
| Căn hộ | 175 | 2.365 |
| Phòng trọ | 257 | 0.986 |

MAE chung chưa làm tròn: 1,544,409.34 VND/tháng; RMSE chung: 2.779 triệu; R²: 0.7354. R² không phải phần trăm dự đoán đúng.

So sánh đúng trên cùng 432 target và các feature phòng ngủ đã được audit lại: legacy champion có MAE 1,559,244.68 VND/tháng; candidate mới cải thiện khoảng 0.9514%. Nhóm phòng trọ tăng MAE khoảng 4.32% so với legacy được đánh giá lại, vẫn nằm trong guard 5%. Không dùng điểm legacy được lưu trước khi sửa ngữ nghĩa phòng ngủ như một so sánh cùng điều kiện.

Probe trên 5,292 đầu vào hợp lệ ghi nhận 0 bước giảm diện tích/phòng ngủ của candidate; legacy có 1,719 vi phạm trên cùng phép thử. Vì legacy vi phạm hợp đồng hành vi, gate dùng nhánh sửa hợp đồng thay cho yêu cầu cải thiện MAE ít nhất 1%; các guard per-category, ngân sách MAE tuyệt đối và data-quality checks vẫn áp dụng.

`bedrooms` gốc không bị sửa; `bedrooms_analysis` và `bedrooms_origin` ghi bằng chứng phòng ngủ riêng/studio. Do coverage dưới 35%, champion bỏ feature phòng ngủ riêng cho phòng trọ; căn hộ vẫn sử dụng feature này. Phân bố tin đủ điều kiện giá, benchmark IDs và target giữ nguyên sau lần sửa này. Xem [hành vi model](MODEL_BEHAVIOR.md).

Benchmark đã được EDA, đã góp phần vào quyết định scope và được tái dùng. Nó không nằm trong training, nhưng không phải external holdout mới. Để đánh giá khả năng tổng quát theo thời gian cần một đợt tin mới được giữ lại trước mọi lựa chọn.

Đợt khởi tạo này dùng `train` trên snapshot có sẵn đã được xem xét; metadata ghi `input_mode=existing_snapshot`. Luồng `refresh` tự động sẽ chặn promotion khi crawl lỗi/thiếu ranh giới. Việc bootstrap không phải chứng nhận nguồn Alonhadat đã crawl đầy đủ.

Kiểm tra local của lần sửa hành vi: 52 pytest và 4 browser E2E đạt; build frontend Node 22 và HTTP smoke đạt. [Verification report](../reports/verification_behavior.json) ghi checksum code/artifact, không giao nhau ID/nhóm trùng train–benchmark, target/dữ liệu gốc không đổi và state round-trip dự đoán/bằng chứng đạt. Docker build chưa chạy vì daemon không sẵn sàng; triển khai từ xa chưa chạy theo lựa chọn local của người dùng.

Xem [EDA](../reports/eda_report.md), [modeling](../reports/modeling_report.md), [pipeline decision](../reports/pipeline_latest.json) và [kiến trúc](ARCHITECTURE.md).
