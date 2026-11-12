# Người 2: Làm sạch và kiểm định dữ liệu

[Phân công chung và số liệu hiện tại](../TEAM_PRESENTATION_GUIDE.md). Đọc file này để chuẩn bị phần của mình; các lệnh đều chạy từ gốc project, sau khi cài đặt theo [README](../../README.md). Môi trường demo là local, chưa có VPS/domain.

## Code và tài liệu cần đọc

- `src/hanoi_rentals/eda_audit.py`, `layout.py`, phần chuẩn hoá đơn vị ở `ingestion/normalization.py` (phối hợp Người 1).
- `tests/test_eda.py`, `tests/test_layout.py`, `data/analysis/review_queue.csv`.
- `reports/data_dictionary.md`, `data/analysis/listings_analysis.csv`, [quy ước phòng ngủ](../MODEL_BEHAVIOR.md).

## Trách nhiệm và bàn giao

Nhận snapshot và raw evidence từ **Người 1**. Bạn sở hữu audit: kiểm tra giá/diện tích, scope, missingness về ngữ nghĩa, phòng ngủ riêng, nhóm trùng và quyết định review có truy vết. Bàn giao **Người 3** analysis dataset, data dictionary, review queue, eligibility flags và `split_group`; **Người 4** sử dụng đúng cùng population/nhóm khi chia tập.

Audit không thay dữ liệu gốc bằng số “đẹp hơn”, không tự điền thiếu để làm EDA và không loại hàng theo lỗi benchmark. Chương trình `eda` hiện gọi cả audit và báo cáo; Người 2 sở hữu logic audit, Người 3 sở hữu phân tích/hình/báo cáo, dù dùng chung một lệnh CLI.

## Kiến thức cần nắm

**Chuẩn hoá đơn vị.** Ví dụ `200.000 đồng/m²/tháng`, diện tích 50 m², có thể tương ứng tổng 10 triệu/tháng. Nếu nguồn đã lưu numeric price là 10 triệu thì không được nhân thêm 50 lần nữa. Phải đối chiếu price text, numeric price và diện tích để quyết định. Những đơn vị ngày/người hoặc giá thoả thuận không được tự chuyển sang tháng bằng giả định tuỳ tiện.

**Missing không phải zero.** Không biết phòng ngủ khác với căn studio có 0 phòng ngủ riêng. Không biết nội thất khác với không có nội thất. Giá trị thiếu được biểu diễn rõ để bước feature xử lý đúng.

**Phòng ngủ riêng và bằng chứng.** `bedrooms` gốc giữ nguyên, `bedrooms_analysis` mới là giá trị dùng phân tích; `bedrooms_origin` ghi vì sao tin được hiểu là studio 0, một số phòng cụ thể hoặc chưa rõ. Tiêu đề có mẫu rõ như `studio`, `1PN`, `2N1K` có thể bổ sung bằng chứng layout. Với phòng trọ, số phòng do nguồn cung cấp có thể là tổng số phòng cả toà nhà: thiếu mô tả layout rõ thì coi chưa xác minh, không mượn nó làm số phòng ngủ riêng của một phòng thuê. Tiêu đề mâu thuẫn hoặc layout không hợp lý làm feature thiếu, không làm sửa dữ liệu gốc.

**Data contract.** Schema là hợp đồng giữa các module: tên trường, kiểu, đơn vị, category cho phép và ý nghĩa. Một cột số đúng dtype vẫn có thể sai ngữ nghĩa, ví dụ diện tích sàn chung bị ghi thành diện tích phòng. Kiểm tra schema và kiểm tra nghiệp vụ cần cùng tồn tại.

**Kiểm định scope.** Chỉ giữ bài toán giá chào thuê theo tháng cho một căn hộ hoặc phòng trọ. Nhà riêng, giá bán, thuê theo ngày/người, ở ghép và thuê cả toà không được lẫn vào population. Keyword là tín hiệu để rà soát, chưa thay thế bằng chứng. Dòng chưa rõ phải được ghi pending hoặc trạng thái phù hợp; không tự cho là hợp lệ.

**Raw fields và analysis fields.** Giữ `price_vnd`, `area_m2`, `bedrooms` gốc để truy vết; tạo riêng `price_month_vnd`, `area_analysis_m2`, `bedrooms_analysis`, `bedrooms_origin`. Một giá trị đáng ngờ có thể khiến feature thiếu trong khi dòng vẫn đủ điều kiện cho thống kê giá. Không gọi mọi dòng thiếu diện tích là dòng không có giá hợp lệ.

**Eligibility theo mục đích.** `include_price` đánh dấu tập giá đủ điều kiện; `include_ppm2` còn cần diện tích hợp lệ. Vì vậy mẫu dùng giá/m² có thể nhỏ và lệch cơ cấu hơn mẫu giá tháng. Không gộp các mẫu số này vào một tổng duy nhất.

**Tin trùng và nhóm phụ thuộc.** ID trùng là lỗi bản ghi; ID khác vẫn có thể cùng một căn đăng lại. `duplicate_group_id`/`split_group` dựa trên tín hiệu bảo thủ, không phải xác minh căn thật. Tạo nhóm không dựa vào giá để giữ peer trong cùng partition. Người 4 chịu trách nhiệm kiểm tra train/validation/benchmark không chia cắt nhóm.

**Review queue và khả năng tái lập.** Lưu quyết định scope/price/area, ghi chú và người review trong `review_queue.csv`. Khi dữ liệu nguồn liên quan đã đổi, không áp dụng âm thầm quyết định cũ; context validation phải phát hiện quyết định stale. Quyết định keep/exclude/unresolved cần có lý do và được dùng nhất quán ở lần chạy lại.

**Outlier khác lỗi.** Giá cao có thể hợp lệ. Percentile flags phục vụ rà soát, không phải quyền xoá đuôi giá. Chỉ điều chỉnh khi có bằng chứng về scope/đơn vị/sai dữ liệu, trước khi tối ưu theo lỗi test. Báo số dòng bị loại, lý do và ảnh hưởng cơ cấu.

**Quy tắc diện tích và phòng ngủ.** `layout.py` dùng giới hạn sản phẩm: số phòng ngủ tối đa `min(cap, max(0, floor((area − 8)/10)))`, cap căn hộ 6 và phòng trọ 2. 10 m²/5 phòng ngủ riêng không hợp lý theo ứng dụng. Đây là heuristic, không phải quy chuẩn pháp luật. Audit giữ giá trị gốc và bỏ feature phòng ngủ không hợp lý; backend của Người 5 kiểm tra lại request theo cùng policy.

## Kịch bản 5 phút, khoảng 3 slide

| Mốc | Nội dung và bằng chứng |
| --- | --- |
| 0:00–1:00 | Phân biệt bảng processed với tập đủ điều kiện; raw fields khác analysis fields |
| 1:00–2:00 | Ví dụ giá/m² bị nhân hai lần, giá theo ngày hoặc tin ngoài scope |
| 2:00–3:00 | Studio 0 khác unknown; số phòng cả toà khác phòng ngủ riêng; mở bedrooms_origin |
| 3:00–4:00 | Review queue, pending và nhóm trùng; tại sao không xoá outlier tuỳ ý |
| 4:00–5:00 | Tổng trước/sau audit, include_price/include_ppm2 và bàn giao cho Người 3/4 |

Câu chuyển: “Tập giá và các trường phân tích đã có tiêu chí rõ ràng. Phần tiếp theo xem mẫu này đang phản ánh nhóm nào, lệch ở đâu và có thể dùng những đặc trưng nào.”

## Câu hỏi phản biện

| Câu hỏi | Ý cần trả lời |
| --- | --- |
| Thiếu diện tích có loại dòng khỏi tập giá không? | Không mặc định; tách điều kiện thống kê giá tháng và giá/m² |
| Vì sao không điền phòng ngủ thiếu bằng 0? | 0 là studio đã biết, missing là chưa rõ; điền 0 làm sai nghĩa |
| Vì sao số phòng nguồn ghi 1 mà analysis lại thiếu? | Có thể là số phòng/toà chứ không phải phòng ngủ riêng; cần title/evidence và origin |
| Giá 100 triệu có bị loại ngay không? | Không chỉ vì cao; phải xem đúng đơn vị, scope và bằng chứng |
| Review cũ có tự áp cho bản ghi đã thay giá không? | Không; kiểm tra context để tránh dùng quyết định hết hiệu lực |
| Dữ liệu được dedup xong có chắc là mỗi dòng một căn? | Không; nhóm trùng tiềm năng vẫn có thể bỏ sót hoặc gom nhầm, cần công khai giới hạn |
| Ai chịu trách nhiệm split không rò rỉ nhóm? | Người 2 tạo nhóm; Người 4 thực hiện và kiểm chứng chia tập |

## Demo và tiêu chí hoàn thành

Đối chiếu ba dòng: giá có đơn vị cần xác minh, studio rõ ràng, phòng trọ có số phòng nguồn chưa xác minh. Cho thấy raw vẫn giữ nguyên, analysis/origin có lý do, queue tái dùng được và flags theo đúng mục đích. Mở `tests/test_eda.py`, `tests/test_layout.py` và data dictionary để liên hệ quy tắc với kiểm tra. Không sửa review trực tiếp chỉ để làm điểm model đẹp.
