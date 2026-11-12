# Người 5: Frontend, Backend và MLOps

[Phân công chung và số liệu hiện tại](../TEAM_PRESENTATION_GUIDE.md). Đọc file này để chuẩn bị phần của mình; các lệnh đều chạy từ gốc project, sau khi cài đặt theo [README](../../README.md). Môi trường demo là local, chưa có VPS/domain.

## Code và tài liệu cần đọc

- `frontend/src/`, `frontend/tests/`, `src/hanoi_rentals/api.py`, `tests/test_api.py`.
- `pipeline.py`, `registry.py`, `state.py`, `.github/workflows/`, `Dockerfile`, `compose.yml`, `deploy/`, `scripts/`.
- [Kiến trúc](../ARCHITECTURE.md), [triển khai](../DEPLOYMENT.md), [đối chiếu MLOps](../MLOPS_REFERENCE_NOTES.md), [review UI](../UI_REDESIGN_REVIEW.md).

## Trách nhiệm xuyên suốt: frontend + backend + MLOps

Một người sở hữu đường đi từ thao tác trên web đến model đang phục vụ, và từ lịch crawl đến việc cập nhật model đó. Không tách MLOps thành một người khác. Nhận crawler của Người 1, audit của Người 2, EDA/feature plan của Người 3 và artifact/evaluation của Người 4; tích hợp bằng CLI, API và workflow hiện có.

Phần này rộng nhất, nên dành **10 phút và khoảng 6 slide**, trong đó có demo sản phẩm. Không cộng nguyên hai bài web 6 phút và MLOps 7 phút thành bài 13 phút. Người 4 trình bày sâu metric/thuật toán/ngưỡng model; bạn tập trung tích hợp, vòng đời artifact và vận hành. Tests crawler/audit/model do người sở hữu từng phần chuẩn bị, bạn chạy chúng trong CI và sở hữu API/E2E/smoke tests.

## A. Website và API

### Trách nhiệm phần web

Bạn biến artifact thành một sản phẩm sử dụng được. Backend kiểm tra request, nạp champion, dự đoán và trả metadata; frontend hướng dẫn nhập đúng, phân biệt bắt buộc/tuỳ chọn, thể hiện loading/error/result và hỗ trợ màn hình nhỏ. Model scoring không được viết thành một bản khác trong JavaScript.

### Hợp đồng API

| Trường request | Bắt buộc? | Ý nghĩa |
| --- | --- | --- |
| `category` | Có | `can_ho_chung_cu` hoặc `nha_tro` |
| `district` | Có | Vị trí từ danh sách schema hỗ trợ |
| `area_m2` | Có | Diện tích lớn hơn 5 và không quá 500 m² theo giới hạn API hiện tại |
| `bedrooms` | Không | Số phòng ngủ riêng: studio/open-plan là 0, chưa rõ để trống; tối đa theo diện tích và cap căn hộ 6/phòng trọ 2 |
| `furnishing` | Không | `Unknown`, `Furnished`, `Unfurnished` |

| Endpoint | Vai trò trong demo |
| --- | --- |
| `GET /api/health` | Trạng thái dịch vụ/model sẵn sàng |
| `GET /api/schema` | Danh sách lựa chọn và hợp đồng đầu vào |
| `POST /api/predict` | Dự đoán từ đầu vào được validate |
| `GET /api/model` | Thông tin model đang được phục vụ và kết quả đánh giá |
| `GET /api/market` | Thống kê mẫu tin trong phạm vi dữ liệu, không nhận là toàn thị trường |
| `GET /metrics` | Số đo vận hành cho theo dõi |

### Kiến thức phải hiểu

**HTTP và JSON.** Frontend gửi một JSON request; backend trả JSON có status phù hợp. HTTP 200 nghĩa request xử lý thành công, không có nghĩa giá đúng thực tế. JSON number không tự mang đơn vị, nên tên trường/schema và nhãn UI phải nói rõ m² và VND/tháng.

**Validation hai lớp.** Trình duyệt giúp người dùng nhập nhanh và thấy lỗi gần trường. Backend vẫn phải kiểm tra vì client có thể bị bỏ qua bằng curl hoặc một chương trình khác. Pydantic/FastAPI kiểm tra category, kiểu số và ràng buộc; đầu vào ngoài scope phải bị từ chối rõ.

**Bắt buộc và tuỳ chọn.** Không gửi chuỗi rỗng như một số hoặc tự gửi 0 cho trường optional chưa nhập. Giữ `null`/bỏ trường theo hợp đồng. Form cần label hiển thị, helper text, error dễ hiểu và có thể thao tác bàn phím.

**Layout hợp lý theo chính sách sản phẩm.** UI đọc policy từ API và tính giới hạn `min(cap_category, floor((area_m2 − 8)/10))`, chặn dưới ở 0. Quy tắc dành 8 m² cho diện tích chung và 10 m² mỗi phòng ngủ riêng, với cap căn hộ 6/phòng trọ 2. Đây là heuristic để không nhận cấu hình như 10 m²/5 phòng ngủ, không phải luật hay bản vẽ được xác minh. Backend phải kiểm tra cùng logic; studio 0 vẫn hợp lệ khi phòng ngủ không ngăn riêng. Thay đổi Unknown sang 0 là thay đổi ý nghĩa, không phải chỉ đổi cách hiển thị.

**Nạp model một lần.** Artifact nạp trong vòng đời ứng dụng thay vì đọc joblib từ đĩa mỗi request. Điều này giảm thời gian và bảo đảm các request dùng model đã được khởi động/kiểm tra. Joblib/pickle chỉ nạp từ artifact tin cậy vì deserialize có thể thực thi code.

**Preprocessing nhất quán.** Cùng model artifact thực hiện impute, encode, target inverse và clipping. Nếu backend tự đổi `bedrooms=None` thành 0 hoặc tự log đầu vào sai, đó là training/serving skew.

**Liveness, readiness và chất lượng.** Liveness: tiến trình còn sống; readiness: đã nạp model, đủ điều kiện nhận request; quality: model dự đoán tốt trên dữ liệu phù hợp. Health xanh chưa chứng minh quality. Nếu artifact hỏng/chưa có, backend phải có trạng thái lỗi hoặc chưa sẵn sàng thay vì trả giá giả.

**Loading, lỗi và request cũ.** Khi submit phải có phản hồi tiến trình và không để nhiều request khiến kết quả cũ ghi đè kết quả mới. Khi API lỗi, giữ dữ liệu người dùng đã nhập, hiển thị thông báo và cách thử lại. Kết quả phải có tóm tắt input để người dùng phát hiện nhập nhầm.

**Same-origin và CORS.** Khi frontend đã build được FastAPI/nginx phục vụ chung domain, request tương đối `/api/...` giảm cấu hình CORS. Dev server riêng có thể proxy API. Không mở CORS tuỳ ý chỉ để che lỗi cấu hình.

**Thống kê tương tự và bất định.** Median/IQR của tin cùng nhóm cho bối cảnh mẫu. Chúng không phải confidence interval của dự đoán cá nhân. UI phải ghi số mẫu và cách nhóm; nếu quá ít mẫu, nói không đủ thay vì vẽ một biểu đồ có vẻ chắc chắn.

Số tin hỗ trợ phải dựa vào training và vùng category/vị trí/diện tích phù hợp với request. Tổng số tin cả quận không thay cho lượng hỗ trợ cục bộ. Tại Hai Bà Trưng, vùng 50 ± 12.5 m² hiện có 21 tin căn hộ (median giá chào 7.5 triệu) và 10 tin phòng trọ (median 6.45 triệu); chỉ 1 tin phòng trọ trong nhóm có bằng chứng 2 phòng ngủ riêng. Không đánh đồng support theo diện tích/vị trí với support thêm theo phòng ngủ. UI cần cảnh báo yếu dữ liệu, không tuyên bố đó là một mức giá thị trường chắc chắn. Champion không dùng bedroom feature cho phòng trọ nên kết quả ở 0/1/2 phòng hợp lệ giữ nguyên; căn hộ có sử dụng feature này.

**Testing.** API test bao gồm payload đúng, thiếu trường bắt buộc, category `nha_rieng`, diện tích âm, dữ liệu không phải số, studio 0, optional bị bỏ trống, layout 10 m²/5 phòng ngủ và model chưa sẵn sàng. Probe model kiểm tra chuỗi layout hợp lệ khi tăng diện tích/phòng ngủ, không đánh đồng Unknown với 0. Frontend cần kiểm tra render, validation theo policy API, trạng thái loading/error, feature thực dùng, support warnings và responsive; build thành công chưa chứng minh mọi luồng tương tác đúng.

### Demo API ngắn

Sau khi chạy backend theo README:

```bash
curl --fail http://localhost:8000/api/health
curl --fail http://localhost:8000/api/schema
curl --fail -X POST http://localhost:8000/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"category":"can_ho_chung_cu","district":"Cầu Giấy","area_m2":60,"bedrooms":2,"furnishing":"Furnished"}'
```

Thử thay category thành `nha_rieng` để chứng minh API từ chối. Đừng trình bày lỗi hợp đồng này như một HTTP 500 của server.

### Câu hỏi và cách trả lời

| Câu hỏi | Ý cần trả lời |
| --- | --- |
| Người dùng nhập tất cả trường có luôn chính xác hơn không? | Chỉ có cơ hội cung cấp thêm tín hiệu; dữ liệu nhập sai hoặc model chưa học tốt vẫn có thể làm sai |
| Vì sao không hỏi địa chỉ/ảnh/tiện ích? | Model hiện chưa dùng các trường đó; hỏi chỉ những thông tin có vai trò rõ |
| Frontend đã có min/max, cần backend kiểm tra nữa không? | Có; mọi client đều có thể gọi trực tiếp API |
| Website có ra giá nhà riêng không? | Không, cả schema API lẫn model đều giới hạn hai category |
| Sao không hiện “confidence 90%”? | Model hồi quy chưa có khoảng dự đoán đã hiệu chỉnh; hiển thị số đó sẽ gây hiểu nhầm |
| Một phòng khép kín chỉ có chỗ ngủ thì nhập mấy phòng ngủ? | Nếu không ngăn thành phòng ngủ riêng thì chọn studio 0; chưa biết layout thì để trống |
| Giới hạn 8+10 có phải quy chuẩn pháp luật không? | Đây là heuristic nghiệp vụ của ứng dụng để kiểm tra đầu vào, không phải tư vấn pháp lý hoặc xác minh diện tích mặt bằng |

## B. Pipeline, CI/CD và vận hành

### Trách nhiệm phần vận hành

Bạn chịu trách nhiệm liên kết các module thành một hệ thống có lịch chạy, state bền vững, quyết định model và cách triển khai. Không viết lại crawler hay thuật toán ML trong YAML; workflow gọi CLI Python và truyền kết quả giữa các job.

### Kiến thức MLOps cần nắm

**CI, CT và CD.** CI kiểm tra code và tích hợp thay đổi. Continuous training là luồng train/evaluate trên dữ liệu mới. CD đóng gói và triển khai phiên bản đã được chấp nhận. Ba việc có liên quan nhưng trigger và rủi ro khác nhau; một pull request sửa UI không cần tự động crawl toàn bộ website.

**Event, workflow, job, step, runner.** Workflow YAML nằm trong `.github/workflows/`. Event có thể là push, pull_request, schedule hoặc workflow_dispatch. Job thường chạy trên runner riêng; `needs` diễn tả phụ thuộc. Các step trong cùng job chia sẻ filesystem, giữa các job cần artifact/state transfer rõ.

**Lịch đánh giá tháng đã hoàn tất.** `.github/workflows/monthly.yml` khai báo cron `35 0 1 * *` với timezone `Asia/Ho_Chi_Minh`: chạy 00:35 ngày 1 để crawl và đánh giá tháng vừa kết thúc. `scripts/month_window.py` tính phạm vi tháng trước nên xử lý được tháng 28, 29, 30 hoặc 31 ngày. GitHub có thể chạy lịch trễ; trigger thủ công cho phép chỉ định `since` và `until` để chạy bù. Thời gian này diễn ra ngay sau khi tháng kết thúc, không bỏ phần ngày cuối tháng như khi crawl quá sớm.

**Runner tạm thời và storage bền vững.** Một runner mới không có dữ liệu/model của tháng trước. Trước crawl phải restore state. `scripts/github_state.py` tải release `rental-state`, kiểm tra checksum rồi khôi phục bundle dữ liệu/benchmark/registry. Mỗi lần ghi state tạo release `rental-state-<run-id>-<attempt>` và lưu báo cáo, sau đó cập nhật điểm trỏ state gần nhất. Workflow artifacts phục vụ trao đổi/báo cáo có thời hạn. Lỗi restore khác 404 phải dừng, tránh coi mất quyền/token lỗi là lần bootstrap đầu tiên và vô tình tạo lại benchmark.

**Registry.** Registry là danh sách model versions và quyết định candidate/champion kèm metadata, không chỉ là thư mục chứa `.joblib`. Phải biết model nào web đang chạy và vì sao được chọn. State version và image version phải truy vết được.

**Quality gate.** Data checks thất bại hoặc schema không khớp phải chặn promote. Model checks đọc kết quả baseline, từng category và champion trên cùng benchmark. “Train xong” là một trạng thái trung gian. Candidate bị reject vẫn lưu lý do; điều này giúp nhóm hiểu vì sao cuối tháng không deploy.

**Bootstrap thủ công và refresh tích hợp.** `train` chỉ huấn luyện/đánh giá snapshot đã có và có thể dùng để bootstrap registry. `refresh` gọi crawl rồi truyền lỗi/coverage của lần crawl đó vào gate. Vì backfill Alonhadat còn bị chặn, không được lấy một lần `train` riêng làm bằng chứng rằng monthly refresh đã vượt điều kiện coverage. Nếu refresh bị chặn, champion hiện có vẫn được phục vụ.

**Docker image bất biến.** Đóng gói artifact đã được chọn cùng backend và frontend build. Gắn tag theo commit/run/model version hoặc triển khai bằng digest để tránh `latest` thay đổi không truy vết. Không gọi training lần nữa trong Dockerfile sau khi đã gate.

**Build/push/deploy.** Build tạo image; push đưa image lên GHCR; deploy yêu cầu máy phục vụ pull và chạy image. Có workflow file chưa có nghĩa schedule đã bật trên GitHub; push image thành công chưa có nghĩa người dùng truy cập được website.

Ba workflow có tên cụ thể: `ci.yml` kiểm tra code/tests/frontend; `monthly.yml` điều phối dữ liệu và model; `deploy.yml` build/test/push image và rollout có điều kiện. Repository variable `ENABLE_IMAGE_PUBLISH=true` bật publish lên GHCR; `ENABLE_DEPLOY=true` mới bật SSH rollout. Cả hai bước từ xa đang để chưa bật trong bản bàn giao local.

**Secrets và quyền.** Token registry, SSH key và host credentials được lưu trong GitHub Secrets/Environment, không commit vào repo hoặc in log. SSH rollout cần `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`; `DEPLOY_URL` là repository variable tuỳ chọn để kiểm tra public endpoint. Chỉ cấp quyền workflow cần. Host key phải xác minh, không bỏ qua bằng cách tắt kiểm tra tuỳ tiện. Hiện chưa có VPS/domain nên chỉ giải thích cách cấu hình theo hướng dẫn, không demo một lần rollout chưa chạy.

**Concurrency.** Hai refresh chạy cùng lúc có thể ghi đè state hoặc promote sai thứ tự. Workflow cần khoá nhóm chạy phù hợp. Chạy lại phải có thể phân biệt một run đã hoàn tất với một state chưa lưu xong.

**Health check và rollback.** Sau deploy kiểm tra ứng dụng/model sẵn sàng. Nếu container mới không hoạt động, cần trở lại image/model đã biết tốt. Rollback không sửa được data bias, nhưng khôi phục dịch vụ khi phiên bản triển khai bị lỗi.

**Monitoring và drift.** Theo dõi số request, lỗi, latency, model version và phân bố input/prediction. Drift là dấu hiệu dữ liệu đổi, chưa đồng nghĩa sai số tăng. Muốn đo actual error cần thu được nhãn phù hợp; hệ thống hiện chỉ có giá chào đăng, chưa có hợp đồng thực tế. Không log địa chỉ riêng hay nội dung cá nhân không cần thiết.

### Các tình huống lỗi cần trả lời được

| Tình huống | Hành vi mong đợi |
| --- | --- |
| Một nguồn chặn hoặc parser không còn listing | Ghi lỗi/coverage, không coi dữ liệu thiếu là tháng hoàn chỉnh; gate có thể chặn, champion giữ nguyên |
| Candidate có MAE chung tốt nhưng phòng trọ xấu đi vượt ngưỡng | Không promote theo metric chung; lưu subgroup failure |
| Candidate tốt hơn nhưng Docker/API smoke test thất bại | Không kết luận deploy thành công; giữ hoặc quay lại phiên bản đã hoạt động |
| GitHub runner mất hết filesystem | Lần sau restore từ state bền vững, không tạo benchmark mới tuỳ ý |
| Chạy monthly hai lần | Dữ liệu không nhân đôi; concurrency và version metadata kiểm soát cập nhật state |
| Không có SSH host/secrets | CI/build có thể chạy, deploy phải báo chưa cấu hình; không nhận website đã online |
| Drift tăng nhưng chưa có nhãn mới | Báo phân bố đổi; không khẳng định MAE đã tăng nếu chưa đo được |

### Bằng chứng demo nên chuẩn bị

- Kết quả local tests/frontend build đã thực sự chạy. Nếu có GitHub CI run thành công thì dùng thêm run đó; không dựng bằng chứng CI chưa chạy.
- Báo cáo crawl/data audit/gate từ lần chạy đã xác minh; chỉ rõ lệnh chạy là `train` hay `refresh`.
- Model registry trước/sau run, kèm trường hợp reject giữ champion nếu có.
- Image tag/digest và health/model version nếu đã triển khai thật.
- Danh sách cấu hình triển khai còn thiếu nếu mới chạy local. Không dùng screenshot một run cũ để nói lần hiện tại đã deploy.

## Kịch bản chung 10 phút, khoảng 6 slide

| Mốc | Nội dung và bằng chứng |
| --- | --- |
| 0:00–1:00 | Kiến trúc browser → FastAPI → champion và nhánh monthly cập nhật artifact |
| 1:00–3:00 | Demo form bắt buộc/tuỳ chọn, studio 0, request hợp lệ và kết quả kèm sai số/version |
| 3:00–4:00 | Demo tổ hợp sai, cảnh báo dữ liệu thưa hoặc input đã sửa; schema/API và không viết lại scoring ở FE |
| 4:00–5:30 | CI/CT/CD, lịch tháng vừa hoàn tất, CLI refresh, restore state và lưu snapshot |
| 5:30–7:00 | Candidate → gate → champion/reject, registry, đối chiếu model version API với artifact |
| 7:00–8:15 | Docker đóng gói FE+BE+model; build/push/deploy khác nhau, local khác VPS |
| 8:15–9:15 | Readiness/metrics, lỗi run, concurrency và rollback; mở tests/run report thật |
| 9:15–10:00 | Kết luận giá trị sản phẩm, giới hạn dữ liệu/benchmark và những phần triển khai chưa cấu hình |

Demo web và mở run report nằm **trong 10 phút này**, không cộng thêm một phiên demo 4 phút riêng. Với câu hỏi thuật toán hoặc tính công bằng của metric, mời Người 4 giải thích; với lỗi nguồn và đơn vị, chuyển Người 1/2.

## Tiêu chí hoàn thành

- Form phân biệt required/optional, studio 0/unknown và không hiển thị giá cũ như ứng với input mới.
- API validate lại, nạp đúng champion một lần, phản hồi có version/feature thực dùng và không nhận nhà riêng.
- Workflow gọi module có sẵn, restore/lưu state, giữ benchmark và không promote khi data/model checks fail.
- Có bằng chứng local build/API/E2E; chỉ nói GitHub Actions/Docker/VPS đã chạy nếu có run thực tế tương ứng.
- Phân biệt lỗi dữ liệu, lỗi model, lỗi API và lỗi triển khai; nêu được hành vi giữ champion/rollback và giới hạn monitoring chưa có nhãn giao dịch.

Câu kết: “Sản phẩm đưa ra giá chào tham khảo có bằng chứng, và chỉ thay mô hình khi đạt kiểm tra; những giới hạn nguồn, benchmark và môi trường triển khai vẫn được công khai.”
