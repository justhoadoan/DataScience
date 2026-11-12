# Người 3: EDA và đặc trưng

[Phân công chung và số liệu hiện tại](../TEAM_PRESENTATION_GUIDE.md). Đọc file này để chuẩn bị phần của mình; các lệnh đều chạy từ gốc project, sau khi cài đặt theo [README](../../README.md). Môi trường demo là local, chưa có VPS/domain.

## Code và tài liệu cần đọc

- `src/hanoi_rentals/eda_reporting.py`; đọc schema đầu ra `eda_audit.py` do Người 2 phụ trách.
- `reports/eda_report.md`, `reports/figures/`, `reports/data_dictionary.md`.
- Phần preprocessing/feature whitelist ở `modeling.py`, [Data card](../DATA_CARD.md).

## Trách nhiệm và bàn giao

Bạn nhận analysis dataset, eligibility flags và split_group từ Người 2, rồi trả lời ba câu hỏi: dữ liệu đang có gì, dữ liệu thiếu/lệch ở đâu, và mô hình được phép dùng thông tin nào. Bàn giao cho Người 4 báo cáo EDA, danh sách feature có lý do và các giới hạn coverage. Không tự viết một bộ audit/loại dòng khác với Người 2; đề xuất thay đổi phải quay lại audit và lưu bằng chứng. Mọi quyết định loại/giữ có evidence và được áp dụng trước khi xem lỗi test mới.

## Kiến thức cần nắm

**Đơn vị quan sát.** Một dòng là listing. Đếm 2.000 dòng không được tự gọi là 2.000 căn duy nhất hoặc 2.000 hợp đồng. Một nhóm có nhiều listing từ cùng người đăng/cùng căn có thể làm sample size có vẻ lớn hơn lượng thông tin độc lập.

**Phân bố giá và thống kê bền vững.** Giá thuê thường lệch phải. Median và IQR mô tả mức điển hình tốt hơn mean khi có đuôi lớn, nhưng không thay thế việc xem cả phân bố. P90/P99 giúp thấy đuôi; một điểm nằm ngoài percentile chưa tự động là lỗi.

**So sánh có điều kiện.** Nguồn A có nhiều phòng trọ hơn nguồn B sẽ có giá gộp thấp hơn, kể cả khi cùng loại căn không chênh lệch nhiều. Nên so theo category, vị trí, khoảng diện tích và đủ số mẫu. Nếu không kiểm soát được hết yếu tố, diễn giải là liên hệ trong mẫu.

**Missingness có cấu trúc.** Thiếu diện tích nhiều hơn ở một nguồn hay một category không phải nhiễu ngẫu nhiên đơn giản. Chỉ phân tích các dòng đủ diện tích có thể làm thay đổi cơ cấu giá. Cần báo cả tỷ lệ thiếu và giá của nhóm có/không có diện tích, cùng giới hạn chọn mẫu.

**Giá theo m².** `price_per_m2 = monthly_price / usable_area`. Chỉ tính khi cả hai đã có ý nghĩa hợp lệ. Không dùng giá/m² làm feature để dự đoán monthly price vì nó đã chứa target.

**Feature engineering và leakage.** Feature hiện có gồm category, vị trí, diện tích, số phòng ngủ và mức nội thất. Giá thô, giá/m², log của giá, title chứa giá, ID và review flags phụ thuộc target không được đưa vào predictor. Dùng `log(price)` làm target transform là hợp lệ; dùng nó làm input thì không.

Quy tắc đọc một layout rõ từ title chỉ tạo feature phòng ngủ và lưu bằng chứng; nó không đưa toàn bộ title vào model. Phải kiểm tra coverage của `bedrooms_analysis`, khác coverage cột nguồn. Nếu trong chính tập training của một category coverage phòng ngủ đáng tin dưới 35%, mô hình phục vụ bỏ feature phòng ngủ cho category đó. Đây là cách tránh học hiệu ứng yếu hoặc mượn nhầm hiệu ứng căn hộ cho phòng trọ; nó không biến Unknown thành studio 0.

**Tiền xử lý phải học từ train.** Median điền thiếu, mean/std chuẩn hoá và danh mục one-hot phải fit trong mỗi training fold. Nếu fit trên toàn bộ bảng trước khi chia, validation đã ảnh hưởng preprocessing. Có một scikit-learn Pipeline giúp giữ ranh giới này.

**One-hot và unknown category.** Loại căn chỉ có hai giá trị nghiệp vụ hợp lệ. Vị trí chưa gặp có thể được mô hình encoder xử lý, nhưng không có nghĩa độ chính xác ở vị trí đó đã được kiểm chứng. API/giao diện cần báo phạm vi hỗ trợ đúng với schema.

**Missing indicator.** Điền median giúp model nhận đủ số, cờ missing giữ lại việc giá trị ban đầu không có. Tuy nhiên cờ này có thể gián tiếp phản ánh nguồn đăng hơn là đặc điểm căn. Vì thế cần đánh giá theo nguồn và thận trọng khi chuyển sang nguồn mới.

**Phân tích nhạy cảm.** Thử giữ một bản ghi mỗi nhóm trùng, thêm nhóm scope còn pending hoặc trim tails để xem kết luận EDA có đổi mạnh không. Những kiểm tra này không cho phép sau đó xoá các lỗi test để cải thiện điểm chính.

## Kịch bản 5 phút, khoảng 3 slide

| Mốc | Nội dung nói và bằng chứng |
| --- | --- |
| 0:00–0:45 | Đơn vị listing, tập giá và câu hỏi EDA |
| 0:45–1:45 | Cơ cấu nguồn/category và so sánh có điều kiện |
| 1:45–2:45 | Missingness, phân bố giá/diện tích và bias của mẫu |
| 2:45–4:00 | Feature whitelist, leakage giá/m², unknown và train-only preprocessing |
| 4:00–5:00 | Một kiểm tra nhạy cảm, giới hạn và bàn giao feature plan cho Người 4 |

Câu chuyển: “Dữ liệu có liên hệ giữa đặc điểm căn và giá, nhưng để biết có dự đoán được không, cần so với một baseline và đo sai số trên các bản ghi chưa dùng để fit.”

## Câu hỏi phản biện

| Câu hỏi | Ý cần trả lời |
| --- | --- |
| Giá tăng khi diện tích tăng có phải quan hệ nhân quả? | Đây là liên hệ trong mẫu; còn vị trí, chất lượng, tiện ích và cơ cấu nguồn chưa kiểm soát hết |
| Vì sao không dùng toàn bộ title? | Title có thể chứa trực tiếp giá và thông tin khó kiểm soát; baseline dùng feature có cấu trúc, NLP là một thử nghiệm riêng có chống leakage |
| Bỏ missing area có sạch hơn không? | Có thể loại có hệ thống một phân khúc; giữ/loại phải dựa vào mục đích, báo coverage và kiểm tra bias |
| Nhiều dữ liệu có luôn tốt hơn? | Dữ liệu lệch phạm vi hoặc sai đơn vị có thể làm model kém; phải tăng dữ liệu có chất lượng và độ phủ hữu ích |
| Vì sao không có ward-level model? | Địa chỉ giữa các phiên bản hành chính chưa được hoà giải và nhiều ô nhỏ thiếu mẫu; không trình bày độ chi tiết vượt bằng chứng |

Demo: mở `reports/eda_report.md`, chọn ba hình có câu chuyện rõ nhất, và chỉ một dòng analysis dataset để chứng minh raw fields được giữ riêng khỏi analysis fields.

## Tiêu chí hoàn thành

Chọn ba hình EDA có câu chuyện và số mẫu rõ; giải thích được một bias, một missingness pattern và một feature bị cấm do leakage. Phân biệt phần Người 2 quyết định tính hợp lệ của bản ghi với phần mình phân tích tác động các quyết định đó. Đề xuất feature không được dùng thống kê benchmark để fit imputer/encoder; Người 4 triển khai preprocessing bên trong mỗi training fold.
