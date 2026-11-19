# Báo cáo Day 09 — Nguyễn Anh Tiến, 2A202603120

## 1. Kết luận trước

Kết luận **Hold**. Pipeline quét 224 ảnh, loại 31 ảnh ở cửa nhận và giữ 193 ảnh. Sau tự sửa và mô phỏng duyệt 80/121 ảnh trong hàng đợi, không còn lỗi ERROR, nhưng 34/193 ảnh còn cảnh báo chưa xử lý (17,62%), cao hơn ngưỡng Hold 10%. `clean_v1` gồm 193 ảnh và manifest ghi quyết định Hold.

## 2. Lỗi và phân việc

Cửa nhận loại 31/224 ảnh: `BAD_SIZE` 3, `CORRUPT_IMAGE` 2, `DUP_IMAGE_EXACT` 8, `DUP_IMAGE_NEAR` 7, `LEAK_TEST` 11. QC vòng 1 trên 193 ảnh còn lại có 36 lỗi bắt buộc và 149 cảnh báo.

| Mã lỗi bắt buộc (vòng 1) | Số lỗi / mẫu số | Xử lý | Lý do |
|---|---:|---|---|
| `BAD_CLASS_ID` | 6 dòng / 193 ảnh | Máy: bỏ dòng | ID ngoài 0–3 |
| `BAD_CLASS_NAME` | 2 mục / 1 data.yaml | Máy: sửa names | Tên lớp sai hoa/thường |
| `BAD_FORMAT` | 3 dòng / 193 ảnh | Máy: bỏ dòng | Thiếu cột hoặc số không hợp lệ |
| `BOX_OUT_OF_IMAGE` | 8 dòng / 193 ảnh | Máy: cắt box | Box tràn biên ảnh |
| `BOX_ZERO` | 4 dòng / 193 ảnh | Máy: bỏ dòng | Box có cạnh bằng 0 |
| `DUP_BOX` | 7 dòng / 193 ảnh | Máy: bỏ dòng | Box lặp cùng lớp |
| `MISSING_LABEL_FILE` | 6 ảnh / 193 ảnh | Người: gán nhãn | Máy không tự bịa nhãn an toàn |

149 cảnh báo vòng 1 gồm `BOX_HUGE` 3, `BOX_TINY` 6, `CLASS_RARE` 4, `EMPTY_LABEL` 11, `POSSIBLE_FALSE_POS` 28, `POSSIBLE_LOOSE_BOX` 27, `POSSIBLE_MISSING` 53, `POSSIBLE_WRONG_CLASS` 17. Máy chỉ đưa ra dấu hiệu; người xem ảnh và quyết định ý nghĩa. Autofix ghi 35 thay đổi: bỏ 20 dòng, cắt 8 box, chuyển 6 ảnh thiếu nhãn cho người gán, sửa tên lớp 1 lần. Hàng đợi có 121 ảnh, vượt ngân sách 80. Điểm ưu tiên cộng theo loại cảnh báo; ảnh thiếu nhãn có trọng số cao, còn `img_0020` đứng đầu (11,524) vì có sửa dòng cùng cảnh báo thiếu vật/nhầm lớp. Mô phỏng duyệt đã xử lý 80 ảnh; đây không thay thế việc người học tự kiểm nhãn khi nộp.

## 3. Calibration (2 ngưỡng)

| Tham số | Khởi đầu | Đã chọn | Precision / Recall trước → sau | Lý do |
|---|---:|---:|---|---|
| `duplicates.phash_dist` (near) | 2 | 16 | 1,00 / 0,50 → 1,00 / 0,83; exact giữ 1,00 / 1,00 | Tăng recall near-duplicate mà không có FP trên bộ calib; ở 20 precision exact giảm còn 0,33. |
| `second_opinion.conf` | 0,25 | 0,6 | Wrong class 0,56 / 0,83 → 0,62 / 0,83; missing 0,50 / 1,00 → 0,57 / 1,00 | Ưu tiên recall 1,00 cho cảnh báo thiếu nhãn; ngưỡng 0,8 tăng precision wrong-class lên 1,00 nhưng recall missing giảm còn 0,75. |

Calib chỉ có 39 ảnh nên các tỷ lệ dễ đổi khi gặp phân bố khác. Ở ngưỡng 0,6, `POSSIBLE_LOOSE_BOX` chỉ đạt precision/recall 0,20/0,20; `POSSIBLE_FALSE_POS` là 0,31/1,00. Không nên diễn giải cảnh báo model như nhãn đúng tuyệt đối.

## 4. Cửa chặn và điểm mù

Lần chạy chuẩn hết lỗi ERROR nhưng vẫn Hold vì 34/193 = 17,62% ảnh còn cảnh báo. Để chứng minh gate chặn lỗi bắt buộc, chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: kết quả Rework, mã thoát 20, còn 6 lỗi bắt buộc `MISSING_LABEL_FILE`, và `work/exp_nb/clean_v1` không tồn tại. Vì ngân sách duyệt bằng 0 nên mô phỏng không gán nhãn cho 6 ảnh này; `autofix` chỉ chuyển chúng cho người gán, không tạo file nhãn.

Hai giới hạn có bằng chứng: (1) trên calib, check box lỏng chỉ bắt đúng 1/5 lỗi chèn và có 4 cảnh báo nhầm; một model lớn hơn không thay được mắt người. (2) check nhầm lớp bỏ sót 1/6 lỗi chèn ở ngưỡng đã chọn; model có thể cùng sai với nhãn.

Ghi nhận khi xem ảnh: `img_0001` thiếu box người lính ở giữa; ở `img_0002`, box thứ 2 và ở `img_0005`, box thứ 5 cần chỉnh khung theo quan sát. Hai dòng nhãn hiện có ID lớp 1 (`person`), nên đây là ghi nhận về box, không phải khẳng định sai ID lớp. `img_0007` thiếu một số box car. `img_0004` có file nhãn rỗng: train nhìn thấy trong ảnh nhưng không thuộc 4 lớp dự án (`car`, `person`, `truck`, `bus`), vì vậy không tạo box train. Ảnh cũng có xe ở góc dưới phải; cần xem xét box `car` nếu xe đó thuộc phạm vi gán nhãn. Số 2/5 là thứ tự dòng/box; ID lớp là cột đầu tiên của dòng YOLO.

## 5. Train: raw vs clean

Tôi đã chạy thử cục bộ trên GPU NVIDIA GeForce RTX 3050 Laptop (4 GB VRAM), PyTorch 2.6.0+cu118 và Ultralytics 8.4.214. Cả hai biến thể dùng cùng model khởi tạo `yolo26n.pt`, 20 epoch, ảnh 640 × 640, batch 2, thiết bị CUDA 0 và hai seed 0, 1. Mỗi lượt dùng 40 ảnh validation; đánh giá cuối trên cùng tập test gồm 100 ảnh và 387 đối tượng.

| Biến thể | Ảnh nguồn / ảnh thực sự dùng train | Số seed | mAP50 (TB ± độ lệch chuẩn) | mAP50-95 (TB ± độ lệch chuẩn) | Precision (TB ± độ lệch chuẩn) | Recall (TB ± độ lệch chuẩn) |
|---|---:|---:|---:|---:|---:|---:|
| raw | 224 / 213 | 2 | 0,651 ± 0,017 | 0,462 ± 0,016 | 0,721 ± 0,046 | 0,579 ± 0,025 |
| clean | 193 / 193 | 2 | 0,675 ± 0,001 | 0,465 ± 0,010 | 0,776 ± 0,029 | 0,571 ± 0,051 |

Ở biến thể raw, Ultralytics bỏ qua 11 ảnh hoặc nhãn hỏng/không hợp lệ khi nạp dữ liệu nên thực tế train bằng 213 ảnh; biến thể clean nạp đủ 193 ảnh. mAP50 của clean cao hơn raw 0,024 điểm (0,675 so với 0,651), lớn hơn độ lệch chuẩn của từng bên (±0,017 và ±0,001); clean cũng ổn định hơn rõ rệt giữa hai seed. Ngược lại, mAP50-95 chỉ cao hơn 0,003 (0,465 so với 0,462), thấp hơn độ lệch chuẩn của cả raw (±0,016) và clean (±0,010). Vì vậy, kết quả này chưa cho thấy clean cải thiện rõ độ khít của bounding box. Mỗi biến thể mới chạy hai seed nên độ bất định vẫn lớn; chưa thể khẳng định pipeline luôn cải thiện khả năng tổng quát hóa.

Hai giả thuyết cần kiểm chứng:

1. **Rò rỉ tập đánh giá và ảnh trùng trong raw:** Báo cáo intake ghi nhận 11 ảnh `LEAK_TEST`, 8 ảnh `DUP_IMAGE_EXACT` và 7 ảnh `DUP_IMAGE_NEAR`. Biến thể raw lấy nguyên 224 ảnh nguồn, nên các ảnh này còn được đưa vào tập train; điều đó có thể làm kết quả test bị lệch hoặc khiến một số mẫu được lặp trọng số. Để kiểm tra, tạo một lượt raw đã loại các ảnh rò rỉ và bản trùng, giữ nguyên tập test, model, siêu tham số và seed, rồi so sánh lại các chỉ số.
2. **Cảnh báo nhãn chưa được người duyệt xử lý trong clean:** 34/193 ảnh clean còn cảnh báo chưa xử lý; trong các nhóm cảnh báo có box lỏng (`POSSIBLE_LOOSE_BOX`) và khả năng thiếu box (`POSSIBLE_MISSING`). Các nhãn này có thể ảnh hưởng mạnh hơn tới mAP50-95, vốn yêu cầu box khớp chặt hơn. Để kiểm tra, tự mở và rà soát 34 ảnh, chỉ sửa lỗi được xác nhận từ ảnh, sau đó train lại clean với cùng hai seed và cấu hình, rồi đối chiếu mAP50-95.

`clean_v1` hiện mang quyết định Hold và còn cảnh báo chưa được người duyệt xử lý, nên các số liệu trên mô tả thử nghiệm với dữ liệu hiện trạng; chúng không làm thay đổi kết luận của gate hay xác nhận bộ nhãn đã sẵn sàng phát hành.

Các kết quả từng lượt nằm trong `submission/results/raw_seed0.json`, `raw_seed1.json`, `clean_seed0.json`, `clean_seed1.json`; bảng, số liệu tổng hợp và biểu đồ được tạo tại `submission/results/comparison.md`, `comparison.json` và `comparison.png`.

## 6. Quyết định và ghi chú AI

Kết luận hiện tại là **Hold**. Kết quả này trung thực với số liệu: còn 34/193 ảnh có cảnh báo chưa xử lý, trong khi ngưỡng Hold là 10%. Bài lab cho phép báo Hold; không thay đổi ngưỡng gate hay ngân sách duyệt để ép Release.

AI được dùng để hỗ trợ viết bốn module, rà soát cách chạy và thực hiện thí nghiệm train cục bộ. Yêu cầu là bám docstring và test có sẵn, đọc lớp/ngưỡng từ `cfg`, chỉ sửa dataset làm việc và để `second_opinion` tạo cảnh báo thay vì tự đổi nhãn. Khi rà bản đầu của `autofix`, phát hiện ảnh vừa bị xóa vẫn có thể nhận log `needs_label`; đã thêm điều kiện bỏ qua ảnh trong `remove_images`. Box không còn diện tích sau khi cắt được chuyển thành `drop_line`. Các chỉ số train trong mục 5 được lấy từ kết quả chương trình sau khi chạy, không phải số liệu ước đoán.

Để kiểm tra, đã chạy 50 test riêng của bốn module và 79 test toàn dự án; tất cả đều đạt. Calibration và pipeline cũng đã chạy: pipeline chuẩn ra Hold, mã 10; với ngân sách duyệt 0, gate ra Rework, mã 20 và không xuất dataset. Checker đầy đủ được chạy trong WSL bằng bản gốc của `scripts/check_submission.py`: 79 test pass, 0 lỗi và 0 cảnh báo. `08_summary.json` còn ghi thời gian chạy (`seconds`) và đường dẫn tuyệt đối (`exported`), nên JSON có thể khác byte theo lần chạy hoặc máy; khi đọc kết quả QC, tôi đối chiếu quyết định, số lượng, hash cấu hình và manifest.

**Kế hoạch hành động:** Trước khi nộp, tôi sẽ tự đọc lại bốn module và mở ảnh để xác nhận các ghi nhận ở mục 4. Nếu muốn hướng tới Release, tôi cần tự xem xét và xử lý cảnh báo của ít nhất 15 trong 34 ảnh còn lại, trong giới hạn ngân sách tối đa 80 ảnh; tôi chỉ chỉnh nhãn khi ảnh xác nhận có lỗi. Sau đó tôi sẽ chạy lại pipeline. Chỉ kết luận Release khi không còn ERROR và số ảnh cảnh báo chưa xử lý còn tối đa 19/193 (dưới 10%); nếu chưa đạt, tôi giữ kết luận Hold. Phần so sánh train raw và clean đã được chạy cục bộ và ghi kết quả ở mục 5.
