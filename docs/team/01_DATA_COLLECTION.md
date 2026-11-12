# Người 1: Thu thập dữ liệu

[Phân công chung và số liệu hiện tại](../TEAM_PRESENTATION_GUIDE.md). Đọc file này để chuẩn bị phần của mình; các lệnh đều chạy từ gốc project, sau khi cài đặt theo [README](../../README.md). Môi trường demo là local, chưa có VPS/domain.

## Code và tài liệu cần đọc

- `src/hanoi_rentals/ingestion/sources.py`, `normalization.py`, `crawler.py`.
- `tests/test_crawler.py`, `reports/crawl_latest.json`, `reports/raw_manifest_latest.json`.
- [Data card](../DATA_CARD.md), [bài toán sản phẩm](../PRODUCT_PROPOSAL.md).

## Trách nhiệm và bàn giao

Bạn giới thiệu bài toán trong 45–60 giây rồi trình bày cách thu thập tin căn hộ/phòng trọ tại Hà Nội. Chịu trách nhiệm nguồn, khoảng ngày, pagination, raw cache, schema đầu ra của adapter, ID theo nguồn, append không nhân đôi và báo cáo lỗi/độ phủ. Không quyết định một dòng có đủ điều kiện đưa vào EDA/model; đó là phần audit của Người 2.

Bàn giao cho **Người 2**: `data/processed/listings.csv`, raw response/cache, `reports/crawl_latest.json` và manifest truy vết. Bảng processed đã qua chuẩn hoá ở adapter nhưng vẫn cần audit nghiệp vụ. Cùng Người 2 thống nhất tên cột, đơn vị và cách biểu diễn thiếu; Người 5 gọi CLI crawler trong workflow, không viết lại crawler bằng YAML.

## Kiến thức cần nắm

**Extract–Transform–Load (ETL).** Extract là lấy JSON/HTML; Transform là đưa dữ liệu hai nguồn về cùng schema, đơn vị và kiểu; Load là lưu bảng chuẩn hoá. Một extractor tốt không được giả định mọi phản hồi 200 đều chứa các listing: trang chặn bot hoặc HTML thay đổi cũng có thể có status 200.

**API và HTML parsing.** Một nguồn có JSON thường có kiểu dữ liệu/ID rõ hơn; một nguồn HTML cần selector và có thể đổi cấu trúc trang. Phải biết selector nào lấy title, giá, diện tích, địa chỉ và ngày, rồi có fixture/test bảo vệ những selector quan trọng. Không suy ra trường mới bằng vị trí phần tử nếu nguồn có thuộc tính cấu trúc tốt hơn.

**Pagination và phạm vi lịch sử.** Trang 1 chỉ cho biết một phần dữ liệu hiện còn hoạt động. Muốn có đầu tháng phải đi sâu hơn, theo dõi ngày của listing và điều kiện dừng. Tin ghim hoặc tin được đẩy lại có thể làm thứ tự ngày không tuyệt đối. Nếu dừng vì giới hạn trang hoặc lỗi nguồn, ghi rõ thay vì khẳng định đã lấy đủ tháng.

**Thu thập cuối tháng không tái tạo được toàn bộ tháng.** Những tin đã xoá trước ngày crawl có thể biến mất. Đây là giới hạn chọn mẫu, không có thuật toán ML nào khôi phục chắc chắn những tin chưa quan sát. Khi thuyết trình, dùng biểu đồ số tin theo ngày đăng để minh hoạ độ phủ thực tế.

**Ngày đăng và ngày quan sát.** `posted_date` là ngày nguồn cho biết tin được đăng/cập nhật; `scraped_at` hoặc timestamp quan sát là lúc hệ thống xử lý/lấy dữ liệu. Với snapshot cũ, một trường parser timestamp chưa chắc là download timestamp. Không dùng hai trường này thay thế cho nhau để kể một câu chuyện xu hướng thị trường.

**Khóa bản ghi và tin đăng lại.** ID có prefix nguồn, ví dụ `nt_...` và `alo_...`, giúp hai nguồn không đụng ID. Xoá dòng trùng ID chỉ giải quyết bản ghi trùng hoàn toàn. Cùng một căn có thể được đăng dưới nhiều ID hoặc hai nguồn; nhóm trùng tiềm năng dựa trên nội dung/vị trí hỗ trợ chia tập, chưa chứng minh đã xác minh căn.

**Data contract.** Schema là hợp đồng giữa các module: tên trường, kiểu, đơn vị, category cho phép và ý nghĩa. Một cột số đúng dtype vẫn có thể sai ngữ nghĩa, ví dụ diện tích sàn chung bị ghi thành diện tích phòng. Kiểm tra schema và kiểm tra nghiệp vụ cần cùng tồn tại.

**Retry, backoff và rate limiting.** Khi nguồn trả 429 hoặc lỗi tạm thời, cần giảm tốc/chờ và có số lần thử hữu hạn. Không dùng một vòng retry vô hạn. Raw cache giúp tái parse mà không gửi lại toàn bộ request.

## Kịch bản 5 phút, khoảng 3 slide

| Mốc | Nội dung và bằng chứng |
| --- | --- |
| 0:00–0:50 | Vấn đề so sánh giá thuê, phạm vi hai category và đầu ra sản phẩm |
| 0:50–2:00 | Hai nguồn, JSON/HTML → adapter → bảng chung; đối chiếu raw với một dòng processed |
| 2:00–3:20 | Crawl thêm đầu tháng, pagination, điều kiện dừng, ngày đăng khác ngày quan sát |
| 3:20–4:20 | Retry/429, raw cache, ID và append không trùng; mở coverage report |
| 4:20–5:00 | Giới hạn tin đã xoá/nguồn bị chặn; bàn giao snapshot cho Người 2 |

Câu chuyển: “Tin đã được đưa về một schema chung, nhưng còn phải kiểm tra đúng đơn vị, đúng phạm vi và đúng ý nghĩa từng trường trước khi phân tích.”

## Câu hỏi phản biện

| Câu hỏi | Ý cần trả lời |
| --- | --- |
| Crawl cuối tháng có lấy đủ mọi tin cả tháng? | Không bảo đảm tin đã xoá hay bị nguồn ẩn; chỉ báo phạm vi đã quan sát và lý do dừng |
| Vì sao cần cả posted_date và scraped_at? | Ngày nguồn hiển thị khác thời điểm quan sát; không dùng lẫn để suy ra xu hướng |
| Nguồn trả 429 thì sao? | Retry/backoff hữu hạn, ghi lỗi và coverage; cung cấp trạng thái lỗi cho pipeline |
| Crawl lại có nhân đôi dữ liệu không? | Append theo ID nguồn; cùng một căn có ID khác vẫn cần audit nhóm trùng ở Người 2 |
| HTTP 200 có chắc parser lấy được dữ liệu? | Không; trang chặn hoặc HTML đổi vẫn có thể trả 200, cần kiểm tra schema/listing count |
| Ai chịu trách nhiệm tháng cần crawl trong cron? | Người 5 cấu hình lịch và truyền khoảng ngày; Người 1 bảo đảm crawler thực thi và báo coverage đúng |

## Demo và tiêu chí hoàn thành

Mở một raw response, dòng processed tương ứng và coverage report; chỉ rõ hai category, ngày yêu cầu/ngày đã quan sát và một lỗi nguồn thật. Không live crawl toàn tháng khi thuyết trình. Chứng minh chạy lại không thêm ID trùng, parser có fixture/test và lỗi nguồn được giữ lại trong báo cáo. Không tuyên bố đã thu đủ chỉ vì lệnh thoát không lỗi.
