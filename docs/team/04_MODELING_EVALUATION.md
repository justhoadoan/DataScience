# Người 4: Mô hình và đánh giá

[Phân công chung và số liệu hiện tại](../TEAM_PRESENTATION_GUIDE.md). Đọc file này để chuẩn bị phần của mình; các lệnh đều chạy từ gốc project, sau khi cài đặt theo [README](../../README.md). Môi trường demo là local, chưa có VPS/domain.

## Code và tài liệu cần đọc

- `src/hanoi_rentals/modeling.py`, `behavior.py`, `modeling_reporting.py`; phối hợp `registry.py` với Người 5.
- `tests/test_modeling.py`, `tests/test_benchmark.py`, `tests/test_layout.py`, `tests/test_registry.py`.
- `reports/modeling_report.md`, `data/benchmark/ids.csv`, model metadata/evaluation, [hành vi model](../MODEL_BEHAVIOR.md).

## Trách nhiệm và bàn giao

Nhận dữ liệu đã audit từ Người 2 và feature plan/EDA từ Người 3. Bạn sở hữu thí nghiệm có thể lặp lại, candidate artifact và báo cáo đánh giá. Model chỉ nhận feature được cho phép; artifact phải chứa preprocessing và target inverse cần thiết. Người 5 nạp artifact để dự đoán, không viết lại công thức chuẩn hoá ở backend.

## Kiến thức cần nắm

**Baseline.** Global median trả một giá cho mọi căn. Category median trả median của căn hộ hoặc phòng trọ trong training set. Baseline đơn giản nhưng cần thiết: một model phức tạp chưa có ích nếu không giảm sai số so với cách đoán hợp lý, cùng các hàng validation.

**MAE.** `MAE = mean(abs(y − prediction))`, đơn vị VND/tháng. Ví dụ hai căn sai 1 triệu và 3 triệu thì MAE là 2 triệu. Metric này dễ giải thích cho nghiệp vụ, nhưng không có nghĩa mỗi căn đều sai 2 triệu.

**RMSE.** `RMSE = sqrt(mean((y − prediction)^2))`. Phạt sai số lớn mạnh hơn MAE. Nếu RMSE cao hơn MAE nhiều, cần xem các lỗi lớn, phân khúc đuôi và nhãn sai. Không tự loại các điểm này sau khi đọc test.

**R².** So sánh tổng bình phương sai số với việc đoán mean của chính tập đánh giá. Có thể âm nếu model kém hơn mốc đó; không phải accuracy hoặc phần trăm căn đoán đúng. R² cao có thể do tập có biên độ giá rộng, nên phải đọc cùng MAE và từng category.

**NMAE theo median.** Khi báo `category MAE / category median price × 100`, đây là chỉ số chuẩn hoá theo quy mô nhóm. Nó khác MAPE, vốn tính tỷ lệ sai số từng dòng rồi lấy trung bình. Ghi chính xác cách tính để tránh diễn giải sai.

**Train, validation, benchmark.** Train dùng fit tham số. Các validation folds dùng chọn family/hyperparameters/feature sets. Benchmark được giữ ngoài quá trình fit, dùng so sánh ứng viên và model đang chạy theo chính sách gate. Benchmark hiện tại từng được EDA và dùng khi quyết định scope nên không gọi external/unseen test.

**Grouped splitting.** Tin trùng hoặc đăng lại có thể giống nhau rất nhiều. Nếu một bản ở train và một bản ở validation, điểm có thể đẹp giả. Chia theo `split_group`, mọi peer cùng nhóm phải cùng partition/fold. Khi tích luỹ tháng mới, các peer của nhóm benchmark vẫn không được lọt vào development. Nhóm theo quy tắc bảo thủ vẫn có thể bỏ sót tin được viết lại.

**Cross-validation và OOF.** Với năm folds, mỗi bản development được dự đoán bởi model không fit trên bản đó. Ghép các dự đoán này thành OOF để so sánh cấu hình. Năm điểm fold có thể cho thấy độ biến động, nhưng không tự tạo một confidence interval chuẩn cho thị trường.

**Ridge và Random Forest.** Ridge học quan hệ tuyến tính có regularization; alpha lớn tăng mức co hệ số. Random Forest gộp nhiều cây, mô hình hoá tương tác và quan hệ phi tuyến. `max_depth`, `min_samples_leaf`, `max_features` điều chỉnh độ linh hoạt. Forest không suy ra được đặc điểm chưa có trong dữ liệu và thường không ngoại suy tốt ra ngoài vùng huấn luyện.

Hai family trên hiện dùng để chẩn đoán, không tự động là ứng viên được phục vụ. Forest không có ràng buộc đơn điệu có thể cho giá thấp hơn khi tăng số phòng ngủ, dù MAE tổng thể vẫn tốt. Đó là lý do cần đánh giá cả hành vi theo hợp đồng sản phẩm và sai số.

**Ứng viên đơn điệu, tách theo category.** Grid phục vụ gồm 8 HistGradientBoosting và 4 Random Forest có ràng buộc; grid chẩn đoán riêng gồm 8 Ridge và 16 Forest không ràng buộc. Mỗi ứng viên học riêng căn hộ và phòng trọ, tránh mang quan hệ số phòng từ nhóm này sang nhóm kia. Champion hiện là HistGradientBoosting loss `squared_error` trên target log, ablation C; không gọi loss này là `absolute_error`. Cấu hình vẫn được chọn bằng MAE sau inverse về VND. Ràng buộc đơn điệu yêu cầu giá không giảm khi tăng diện tích hoặc số phòng ngủ riêng đã biết, giữ nguyên vị trí/nội thất/các feature khác và ở layout hợp lệ. Giá có thể giữ nguyên; không bắt buộc mỗi phòng ngủ thêm phải tăng một số tiền cố định. Đây là giả định sản phẩm, chưa phải bằng chứng nhân quả rằng xây thêm phòng sẽ tăng giá thuê.

**Không có thứ tự giá giữa category.** Nhãn phòng trọ có thể chứa CHDV/căn hộ mini mới, trong khi nhãn căn hộ có thể gồm căn cũ. Khi cùng diện tích và số phòng, nhóm phòng trọ không đương nhiên phải rẻ hơn. Thử ép category thành thang giá sẽ che sai lệch chọn mẫu và chất lượng căn chưa được quan sát. Thay vào đó xem số tin training hỗ trợ cục bộ, nguồn và cảnh báo dữ liệu thưa.

**Log target.** Huấn luyện trên log giá có thể giúp giảm ảnh hưởng tương đối của đuôi lớn và phù hợp với thay đổi theo tỷ lệ. Khi dự đoán phải inverse về VND trước khi tính metric phục vụ. `exp(mean(log y))` không bằng `mean(y)`, vì vậy không diễn giải log-model mặc nhiên tối ưu MAE hoặc cho dự đoán không bias. Mục tiêu direct/log phải được chọn bằng validation.

**Ablation.** So A = category/vị trí/diện tích, B = A + phòng ngủ riêng đủ bằng chứng, C = B + nội thất để đo thông tin thêm có hữu ích hay không. CV chọn trong nhóm ứng viên đơn điệu được phép phục vụ; Ridge/Forest vẫn cung cấp mốc chẩn đoán. Feature phòng ngủ có thể bị bỏ riêng ở category thiếu coverage, vì vậy cần đọc danh sách feature thực dùng trong metadata/API thay vì chỉ tên B/C. Cấu hình tốt trên development chưa chắc tốt hơn trên từng nhóm tương lai. Source-aware model dùng để chẩn đoán source bias, không mặc nhiên chọn source làm feature sản phẩm.

**Candidate và champion.** Candidate là model mới vừa được đánh giá; champion là phiên bản registry được web phục vụ. Gate có thể yêu cầu đủ dữ liệu, tốt hơn baseline, không suy giảm vượt ngưỡng theo category, cùng schema và không có dự đoán không hợp lệ. Ngưỡng chính xác đọc từ cấu hình code; không thay sau khi nhìn benchmark.

**Sửa vi phạm hợp đồng đã chứng minh.** Gate còn chạy probe kiểm tra diện tích/phòng ngủ. Nếu champion cũ có vi phạm được đo lại, candidate khắc phục có thể được xem xét mà không cần cải thiện MAE 1%. Mức tăng MAE chung vẫn không quá 10%; giới hạn mỗi category không xấu quá 5%, ngân sách MAE tuyệt đối và data-quality checks vẫn giữ. Đây là một ngoại lệ có lý do và evidence để sửa hành vi, không phải quyền bỏ qua quality gate.

**Benchmark cố định và tái sử dụng.** Giữ cùng các hàng giúp so sánh công bằng. Tuy vậy nhiều vòng lựa chọn dựa vào cùng benchmark sẽ tích luỹ nguy cơ overfit qua quyết định của con người. Cần dữ liệu các tháng tương lai, báo cáo temporal riêng và kế hoạch version benchmark. Không chuyển benchmark cũ vào train trong một monthly refresh thông thường.

## Kịch bản 7 phút, khoảng 4 slide

| Mốc | Nội dung nói và bằng chứng |
| --- | --- |
| 0:00–0:45 | Phát biểu target, baseline và metric chính |
| 0:45–2:00 | Vẽ train/CV/benchmark và nhóm tin đăng lại; giải thích không để benchmark học lại tháng sau |
| 2:00–3:10 | Ridge/Forest chẩn đoán, HGB đơn điệu theo category, direct/log và feature ablations |
| 3:10–4:20 | Mở bảng kết quả baseline/candidate trên cùng rows; chỉ MAE, RMSE, R² |
| 4:20–5:20 | Mở metric riêng căn hộ/phòng trọ và ví dụ lỗi lớn; nói rõ hạn chế |
| 5:20–6:20 | Mở metadata/schema và gate decision; giải thích model nào được phép phục vụ |
| 6:20–7:00 | Giới thiệu artifact đã nạp lại kiểm tra, chuyển cho Người 5 |

Câu chuyển: “Mô hình đã được đóng gói cùng cách xử lý đầu vào; phần web chỉ gọi giao diện dự đoán này và hiển thị kết quả kèm phạm vi sử dụng.”

## Câu hỏi phản biện

| Câu hỏi | Ý cần trả lời |
| --- | --- |
| Bỏ nhà riêng làm MAE giảm có chứng minh model tốt hơn? | Đổi population tự làm metric thay đổi. Chỉ so được bằng cùng các căn hộ/phòng trọ test; phải tách tác động scope và retrain |
| Vì sao không chọn model có R² cao nhất? | Mục tiêu chính là sai số tiền; lựa chọn dựa MAE và bảo vệ các nhóm, R² là bổ sung |
| Vì sao không huấn luyện luôn cả benchmark cho nhiều dữ liệu? | Sẽ mất khả năng so sánh độc lập cho gate. Nếu refit phục vụ theo thiết kế khác cần thêm một holdout mới, metadata và quy trình rõ ràng |
| Có thể nói model chính xác bao nhiêu phần trăm? | Nêu MAE VND/tháng, median/p90 sai số và số mẫu; không biến R² thành accuracy |
| Không có khoảng giá thì UI có thiếu không? | Có thể hiển thị sai số lịch sử và thống kê mẫu tương tự với nhãn đúng; khoảng xác suất cần calibration và kiểm định riêng |
| Model mới không qua gate thì sao? | Registry ghi lý do, champion giữ nguyên; đó là một kết quả đúng của hệ thống kiểm soát chất lượng |
| Tăng phòng ngủ sao giá giữ nguyên? | Đơn điệu nghĩa không giảm. Có thể là một vùng phẳng của model, hoặc feature bị bỏ do category có coverage quá thấp; API phải công khai trường thực dùng |
| Vì sao căn hộ 50 m² lại rẻ hơn phòng trọ 50 m²? | Category không có thứ tự chất lượng; CHDV/căn hộ mini và căn hộ cũ chồng lấn. Kiểm tra hỗ trợ cục bộ, không ép bất đẳng thức giữa nhãn |

Demo: mở báo cáo hiện tại, metadata model và quyết định registry; chạy một dự đoán trực tiếp và xác minh artifact tải lại được. Không sửa ngưỡng gate ngay trên sân khấu để tạo kết quả deploy.

## Bàn giao tích hợp và tiêu chí hoàn thành

Bàn giao Người 5 bundle model, metadata/schema, kết quả benchmark theo category, behavior probe và quy tắc chấp nhận model. Người 4 chịu trách nhiệm ý nghĩa thống kê, ngưỡng chất lượng và bằng chứng ứng viên; Người 5 tích hợp thực thi gate/registry vào workflow và phục vụ đúng artifact. Nếu đổi policy, hai người cùng rà soát; không nới ngưỡng chỉ để có lần deploy thành công.

Tự tính MAE trên ba sai số 1, 2, 3 triệu = 2 triệu/tháng; giải thích được grouped CV, benchmark cố định, loss huấn luyện khác metric lựa chọn và vì sao có đơn điệu. Chứng minh artifact nạp lại giữ dự đoán, benchmark/peer không nằm trong train và một candidate bị reject vẫn là kết quả hợp lệ.
