# UI review: Hanoi Rent Insight

Giao diện là một công cụ ước tính và đọc bằng chứng, áp dụng nhánh **app screens** của [taste-skill](https://github.com/leonxlnx/taste-skill) và [Emil design engineering](https://github.com/emilkowalski/skills). Không áp dụng yêu cầu ảnh quảng cáo hoặc chuyển động cho landing page vào form tính giá.

## Hướng thiết kế và phạm vi

- Style: **Achromatic ledger**, seed **307776374**, không redraw. Khung điều hướng trung tính giúp giá và bằng chứng được chú ý trước.
- Giữ font **Be Vietnam Pro** và màu xanh dữ liệu của dự án; thay nền kem bằng xám trung tính. Tiêu đề 24–26 px, nhãn form 14 px, giải thích 13 px, metadata 12 px; số có tabular figures.
- Điểm riêng: minh hoạ bố trí phản hồi theo số phòng ngủ riêng, phân biệt studio 0 với chưa rõ; bên cạnh giá có số mẫu training gần diện tích đang chọn.
- Chrome: sidebar 230 px desktop, chuyển sang thanh trên ở tablet và điều hướng dưới ở điện thoại. Không dùng icon trong ô màu, gradient hoặc shadow cho panel.
- Dữ liệu lấy từ API và champion thật. Không có số mẫu giả cần thay trước khi sử dụng.

Ba màn hình trả lời ba câu hỏi: “Chỗ ở này có giá chào tham khảo bao nhiêu?”, “Giá chào và số mẫu theo khu vực thế nào?”, “Mô hình dùng dữ liệu gì và sai số ra sao?”.

## Nội dung cần giữ

Form phải có loại căn, quận/huyện, diện tích bắt buộc; số phòng ngủ riêng và nội thất tuỳ chọn. Kết quả phải ghi ngữ cảnh đã gửi, đơn vị theo tháng, sai số lịch sử và giới hạn áp dụng. Người dùng cần thấy số mẫu hỗ trợ, ý nghĩa studio và lý do phòng ngủ chưa được sử dụng cho phòng trọ. Màn thị trường giữ bảng giá thật; màn mô hình giữ phiên bản và benchmark.

| Before | After | Why |
| --- | --- | --- |
| Banner và hình thành phố chiếm màn hình đầu | Form và kết quả xuất hiện ngay | Công việc chính là tính giá |
| Số phòng nhập tự do, thiếu kiểm tra với diện tích | Lựa chọn phụ thuộc diện tích, API kiểm tra lại | Chặn 10 m² / 5 phòng và giải thích tại trường nhập |
| Studio dễ bị hiểu là thiếu thông tin | 0 = không ngăn phòng ngủ; chưa rõ = missing | Giữ đúng ý nghĩa dữ liệu |
| Giá cũ vẫn trông như ứng với thông tin vừa sửa | Kết quả giữ nguyên ngữ cảnh đã gửi và báo cần tính lại | Tránh so sánh nhầm hai cấu hình |
| Cảnh báo và bằng chứng khó thấy | Số tin training gần diện tích ở cạnh giá | Không biến một dự đoán thành giá thị trường chắc chắn |
| Chữ nhỏ, nền kem và nhãn in hoa | Nền trung tính, chữ hỗ trợ 13 px, nhãn câu thông thường | Đọc form và số liệu dễ hơn |
| Feedback thao tác thiếu nhất quán | Focus rõ, hover chỉ cho con trỏ, pressed scale .97, reduced motion | Phản hồi gọn, hỗ trợ bàn phím và điện thoại |

## Ba vòng nhìn và sửa

Baseline: inspector **3 FAIL / 7 WARN**. Đã mở ảnh desktop, tablet, mobile và các ảnh toàn trang. Banner đẩy form xuống dưới, nhãn in hoa và màu trang trí lấn nội dung, nhiều chữ dưới 13 px.

Vòng 1: workspace mới **0 FAIL / 2 WARN**. Hai vấn đề thấy được: chữ giải thích còn nhỏ; nhãn điều hướng tablet bị xuống dòng. Nâng chữ hỗ trợ lên 13 px, giữ nhãn điều hướng trên một dòng. Không kéo giãn panel để lấp khoảng trống.

Vòng 2: **0 FAIL / 1 WARN**. Trên ảnh 390 px, nút tính giá gần bị thanh điều hướng dưới che ở lần nhìn đầu. Rút dòng mô tả lặp lại trên điện thoại để nút hiện trọn; phần giải thích vẫn nằm ở panel kết quả. Không giảm kích thước vùng bấm.

Vòng 3: **0 FAIL / 1 WARN** ở 1440 / 768 / 390 px. Đã mở cả sáu ảnh fold/page của lần cuối. Cảnh báo `ragged-row` còn lại được chấp nhận: form là một khối, cột kết quả là các panel có nội dung và chiều cao thay đổi sau mỗi lần tính; căn bằng đáy sẽ tạo khoảng trống giả trong trạng thái chưa có kết quả. Không dùng `--allow` để tắt kiểm tra.

Source lint: **0 FAIL / 1 WARN** về dấu gạch dài; các dấu `—` chủ yếu là ký hiệu chưa có dữ liệu và dấu phân cách lựa chọn studio, không phải nhãn trang trí.

## Đánh giá ảnh cuối theo câu hỏi app screens

1. **Câu hỏi chính:** tiêu đề nói rõ ước tính giá; sau khi tính, giá là số lớn nhất và mang màu dữ liệu. Chưa tính thì hiện hướng dẫn, không tự gán giá mẫu.
2. **Cạnh và khoảng trống:** form và cột kết quả dùng chung lề/gutter; không có panel rỗng bị kéo cao. Chiều cao cột khác nhau có chủ đích theo nội dung.
3. **Màu và font:** chrome xám, giá xanh, cảnh báo và lỗi có màu riêng. Font Be Vietnam Pro thực sự hiển thị trong phép đo browser.
4. **Số liệu:** tổng 5.739 tin ở workspace và dữ liệu API cùng nguồn. MAE là số benchmark của category; số tin gần diện tích lấy từ development, không cộng vào benchmark. Cột số căn phải, có đơn vị và số mẫu.
5. **0 và thiếu:** 0 hiển thị studio; chưa rõ được gửi `null`. Thiếu giá tham khảo vì dưới 5 mẫu được ghi “Chưa đủ mẫu”; không thay bằng 0.
6. **Chú giải:** không có chart nhiều màu cần legend. Sơ đồ được ghi rõ chỉ minh hoạ khái niệm, không phải mặt bằng căn thực tế.
7. **Điện thoại:** sidebar thu gọn; điều hướng dưới có ba nhãn; form, giá và bằng chứng xếp dọc. Nút chính nhìn thấy ở 390×844, không tràn ngang tại 1440/768/390.

Tự đánh giá cuối: design 7.5, usability 8, creativity 7, content 8 → **7.6/10**. Giới hạn còn lại: bảng và dự đoán phụ thuộc mẫu tin thu thập; bố trí minh hoạ chưa mô tả mặt bằng thật. Không dùng điểm tự đánh giá này làm metric chất lượng model.

## Kiểm tra và ảnh

- Production build TypeScript/Vite thành công trên Node 22.
- Playwright chạy với Chrome thật: 4 luồng pass, gồm đổi phòng ngủ, studio 0 / unknown null, kết quả cũ khi sửa đầu vào, API 422, lỗi tải và retry, điều hướng và điện thoại.
- Reduced motion được hỗ trợ; không có animation xuất hiện nội dung.
- [Báo cáo inspector](../reports/ui_inspection.json), [workspace desktop](screenshots/workspace-desktop.jpg), [workspace mobile](screenshots/workspace-mobile.jpg), [trước sửa](screenshots/workspace-before.jpg).
- [Kết quả desktop](screenshots/estimator-desktop.png), [studio mobile](screenshots/studio-mobile.png), [thị trường](screenshots/market-desktop.png), [mô hình](screenshots/model-desktop.png).
