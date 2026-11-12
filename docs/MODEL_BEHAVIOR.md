# Phòng ngủ, studio và hành vi giá dự đoán

Tài liệu giải thích hợp đồng hành vi của mô hình phục vụ sau khi rà soát các trường hợp người dùng phản ánh. Champion được kiểm tra trong lần sửa này là `ec9a7bf02b42ae3b`; số liệu dưới đây đối chiếu với [verification report](../reports/verification_behavior.json) và metadata của version đó. Đây là kết quả local, chưa phải một lần triển khai VPS/domain.

## 1. Studio 0 khác với chưa biết

`bedrooms` mô tả **số phòng ngủ được ngăn riêng** trong một căn/phòng cho thuê:

- **0:** studio hoặc phòng khép kín có khu vực ngủ chung không gian, không ngăn thành phòng ngủ riêng.
- **1, 2, ...:** số phòng ngủ riêng, không phải số giường hay tổng số phòng trong cả toà nhà.
- **Bỏ trống:** chưa biết layout. Hệ thống giữ là missing; không tự đổi thành 0 hoặc 1.

Một phòng trọ có một không gian dùng để ngủ không đương nhiên có “1 phòng ngủ riêng”. Quy ước này phải được giữ giống nhau ở audit, model, API và form.

Dữ liệu nguồn `bedrooms` được giữ nguyên để truy vết. Audit tạo `bedrooms_analysis` và `bedrooms_origin`: tiêu đề rõ như `studio`, `1PN`, `2N1K` có thể là bằng chứng; mô tả mâu thuẫn thì giữ chưa rõ. Với phòng trọ, số phòng từ nguồn thiếu bằng chứng layout có thể chỉ số phòng của cả toà nhà, nên không được dùng mặc nhiên làm feature phòng ngủ riêng.

## 2. Đầu vào phải phù hợp với diện tích

Ứng dụng dùng heuristic:

```text
8 m² diện tích chung + 10 m² × số phòng ngủ riêng ≤ diện tích nhập
cap căn hộ: 6 phòng ngủ riêng
cap phòng trọ: 2 phòng ngủ riêng
```

Số phòng tối đa là `min(cap_category, max(0, floor((area_m2 − 8)/10)))`. Đây là **quy tắc sản phẩm để kiểm tra tính hợp lý**, không phải quy chuẩn xây dựng, cam kết căn có layout đó, hay kiểm tra pháp lý.

Ví dụ 10 m²/5 phòng ngủ riêng phải bị từ chối; nếu là một phòng khép kín không ngăn ngủ riêng thì người dùng chọn 0. Backend kiểm tra lại dù frontend đã giới hạn lựa chọn. Frontend đọc policy từ API để tránh hai nơi tự dùng hai quy tắc khác nhau.

## 3. Tăng diện tích hoặc phòng ngủ không được làm giá giảm

Hợp đồng mới yêu cầu **không giảm**, khi:

1. Giữ nguyên loại căn, vị trí, nội thất và các đầu vào khác.
2. Chỉ tăng diện tích, hoặc chỉ tăng số phòng ngủ riêng đã biết.
3. Các cấu hình so sánh đều thuộc miền layout hợp lệ.

Giá có thể giữ nguyên ở một khoảng. Hợp đồng không yêu cầu mỗi phòng ngủ thêm phải cộng một số tiền cố định. So sánh Unknown với studio 0 không phải một bước tăng/giảm số phòng đã biết.

Grid ứng viên phục vụ gồm 8 HistGradientBoosting và 4 Random Forest có ràng buộc đơn điệu, học riêng cho căn hộ/phòng trọ; champion hiện được chọn là HistGradientBoosting `squared_error` trên target log, ablation C. 8 Ridge và 16 Random Forest không ràng buộc vẫn có ích để chẩn đoán, nhưng điểm MAE tốt không đủ để bỏ qua hợp đồng hành vi của web. `behavior.py` kiểm tra các lưới đầu vào hợp lệ mà không dùng target benchmark để điều chỉnh giá.

Đơn điệu là giả định phục vụ: người dùng thay một đặc điểm trong cùng ngữ cảnh sẽ không gặp một bước giá giảm trái kỳ vọng đó. Nó chưa chứng minh tác động nhân quả khi cải tạo một căn thật để thêm phòng, vì việc chia phòng còn có thể đổi ánh sáng, công năng và chất lượng sống mà dữ liệu không có.

## 4. Nhập phòng ngủ không bảo đảm feature được dùng

Nếu dưới **35%** training rows của một category có số phòng ngủ riêng đủ bằng chứng, model bỏ feature phòng ngủ cho category đó. Ngưỡng này được tính trên chính tập fit của fold/category, không nhìn benchmark. Việc tách category tránh mang tín hiệu phòng ngủ từ căn hộ sang phòng trọ khi số đếm nguồn phòng trọ thiếu tin cậy.

Khi feature bị bỏ, thay đổi số phòng ngủ hợp lệ có thể không đổi dự đoán. API và giao diện phải nói rõ các feature thực sự được dùng. Không tuyên bố giá đã được điều chỉnh theo phòng ngủ khi model thực tế không sử dụng trường này.

Champion `ec9a7bf02b42ae3b` sử dụng phòng ngủ riêng cho căn hộ nhưng bỏ feature này cho phòng trọ do không đủ coverage. Vì vậy kết quả phòng trọ bằng nhau khi đổi giữa 0, 1 và 2 phòng ngủ hợp lệ là hành vi được giải thích bằng schema của category đó.

## 5. Không ép căn hộ luôn đắt hơn phòng trọ

Category là nhãn nguồn, chưa phải thang chất lượng. Nhóm phòng trọ có thể gồm CHDV hoặc căn hộ mini mới; nhóm căn hộ có thể có căn cũ hoặc các khu vực chưa được phân biệt ở cấp đường/toà nhà. Dữ liệu không có đủ thông tin về chất lượng nội thất, vị trí ngõ, phí dịch vụ hoặc điều kiện thuê để tạo một thứ tự chắc chắn.

Vì vậy việc một phiên bản cho **50 m², 2 phòng ngủ riêng ở Hai Bà Trưng** có giá căn hộ thấp hơn phòng trọ không tự chứng minh một phép tính sai. Cần kiểm tra nhãn, nguồn và số tin training hỗ trợ vùng đó; không sửa bằng cách ép một thứ tự giá giữa category.

Với champion mới, khi nội thất là `Unknown`, căn hộ Hai Bà Trưng 50 m² cho khoảng **8.313 triệu/tháng ở 1 phòng ngủ riêng** và **8.483 triệu ở 2 phòng**. Phòng trọ cùng diện tích/vị trí trả khoảng **6.356 triệu** cho 0, 1 hoặc 2 phòng ngủ, vì category này không sử dụng bedroom feature. Các giá này là kết quả kiểm tra request cụ thể, không phải giá thị trường đã xác minh.

Support endpoint chỉ dùng development, lọc đúng category/quận và diện tích **50 ± 12.5 m²**: căn hộ có **21 tin**, median giá chào **7.5 triệu**; phòng trọ có **10 tin**, median **6.45 triệu**. Trong nhóm phòng trọ đó chỉ **1 tin** có bằng chứng 2 phòng ngủ riêng. Lượng hỗ trợ theo diện tích/vị trí và lượng hỗ trợ thêm theo phòng ngủ là hai số khác nhau; không gọi nhóm này là “chỉ hai tin” hoặc dùng tổng toàn quận để che độ thưa.

Thống kê toàn quận không thay thế coverage cục bộ. Median/IQR của tin trong mẫu cũng không phải prediction interval cho một căn mới.

## 6. Các trường hợp cần kiểm tra

| Trường hợp | Hành vi theo hợp đồng |
| --- | --- |
| Studio hoặc phòng khép kín không ngăn ngủ riêng | Chọn phòng ngủ 0; không coi là giá trị thiếu |
| Chưa biết layout | Bỏ trống; không tự điền 0 hoặc 1 |
| 10 m², 5 phòng ngủ riêng | API từ chối; form giải thích giới hạn và ý nghĩa studio 0 |
| Cùng category/vị trí/nội thất, tăng số phòng ngủ riêng trong miền hợp lệ | Giá không giảm nếu model dùng feature; có thể giữ nguyên |
| Cùng category/vị trí/nội thất/phòng ngủ, tăng diện tích | Giá không giảm |
| Category thiếu coverage phòng ngủ đáng tin | Công khai bỏ feature, không mượn quan hệ từ category khác |
| Căn hộ và phòng trọ cùng 50 m²/2 phòng ngủ | Không áp đặt thứ tự giá; hiển thị hỗ trợ dữ liệu và cảnh báo thưa |

Các phép thử trên kiểm tra logic, không dùng để chọn một giá cụ thể cho ví dụ người dùng. Trong lần kiểm tra local này, 52 pytest và 4 Playwright E2E đạt; probe 5,292 đầu vào hợp lệ ghi 0 vi phạm ở candidate, so với 1,719 vi phạm của legacy trên cùng semantics. Build frontend Node 22 và HTTP smoke đạt. Những kết quả này không thay thế đánh giá chất lượng trên dữ liệu tương lai.

## 7. Sửa hợp đồng vẫn phải giữ ngân sách chất lượng

Gate kiểm tra sai số và hành vi đồng thời. Benchmark vẫn giữ **432 ID và target cũ**, không thêm vào training và không đổi giá benchmark để làm ứng viên tốt hơn.

Khi probe chứng minh champion cũ có vi phạm, một candidate đã sửa hành vi có thể thay nó mà không cần cải thiện MAE thêm 1%. Ngoại lệ sửa hợp đồng vẫn yêu cầu MAE chung không xấu hơn quá 10%, mỗi category không xấu hơn quá 5%, qua ngân sách MAE tuyệt đối, baseline và data-quality checks. Không phải cứ mang tên “sửa lỗi” là được bỏ qua gate.

Lần promote hiện tại dùng đúng nhánh này: MAE candidate **1,544,409.34 VND/tháng**, legacy đánh giá lại với cùng phòng ngủ đã làm sạch **1,559,244.68 VND/tháng**, cải thiện **0.9514%**. MAE căn hộ là **2,364,807.79**, phòng trọ **985,772.26**, R² chung **0.7354**. Phòng trọ xấu hơn legacy khoảng 4.32%, vẫn dưới guard 5%. Benchmark 432 ID/target và tập giá không đổi; điểm legacy lưu từ trước thay đổi ngữ nghĩa phòng ngủ không phải mốc so sánh cùng điều kiện.

Đọc `reports/modeling_report.md`, `reports/pipeline_latest.json`, `artifacts/registry.json` và evaluation của version để biết ứng viên nào đã được chọn, các probe ra sao và champion thực tế là gì. `/api/health` xác nhận version mà tiến trình web đang phục vụ. Bản local hiện vẫn chưa có xác nhận triển khai VPS/domain.
