# Báo cáo Day 09 — Nguyễn Anh Tiến, 2A202603120

## 1. Kết luận trước

Kết luận **Hold**. Pipeline quét 224 ảnh, loại 31 ảnh ở cửa nhận và giữ 193 ảnh. Sau tự sửa và mô phỏng duyệt 80/121 ảnh trong hàng đợi, không còn lỗi ERROR, nhưng 34/193 ảnh còn cảnh báo chưa xử lý (17,62%), cao hơn ngưỡng Hold 10%. `clean_v1` gồm 193 ảnh và có manifest ghi Hold; đây là bản nháp, chưa được phát hành.

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

Lần chạy chuẩn hết lỗi ERROR nhưng vẫn Hold vì 34/193 = 17,62% ảnh còn cảnh báo. Để chứng minh gate chặn lỗi bắt buộc, chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb`: kết quả Rework, mã thoát 20, còn 6 lỗi bắt buộc `MISSING_LABEL_FILE`, và `work/exp_nb/clean_v1` không tồn tại.

Hai giới hạn có bằng chứng: (1) trên calib, check box lỏng chỉ bắt đúng 1/5 lỗi chèn và có 4 cảnh báo nhầm; một model lớn hơn không thay được mắt người. (2) check nhầm lớp bỏ sót 1/6 lỗi chèn ở ngưỡng đã chọn; model có thể cùng sai với nhãn.

Ghi nhận khi xem ảnh: `img_0001` thiếu box người lính ở giữa; `img_0002` box/dòng nhãn số 2 sai; `img_0005` box/dòng số 5 sai; `img_0007` thiếu một số box car. `img_0004` có file nhãn rỗng: train nhìn thấy trong ảnh nhưng không thuộc 4 lớp dự án (`car`, `person`, `truck`, `bus`), vì vậy không tạo box train. Ảnh cũng có xe ở góc dưới phải; cần xem xét box `car` nếu xe đó thuộc phạm vi gán nhãn. Số 2/5 ở đây là thứ tự dòng/box trong ảnh; ID lớp là cột đầu tiên của dòng YOLO.

## 5. Train: raw vs clean

Chưa chạy. Phần train là tùy chọn và cần chạy notebook trên Google Colab với GPU; không có kết quả train nào được tạo hoặc suy đoán trong báo cáo này.

## 6. Quyết định và ghi chú AI

Quyết định cuối là **Hold**; chỉ cân nhắc Release khi không còn ERROR và số ảnh còn cảnh báo chưa xử lý giảm xuống tối đa 19/193 (dưới 10%). Không đổi ngưỡng gate hay ngân sách duyệt.

- Prompt: dùng docstring và test của bốn module để viết đúng vào/ra; đọc ngưỡng từ config; chỉ sửa dataset làm việc; không đọc đáp án trong code QC; model thứ hai chỉ cảnh báo.
- Kiểm tra: 50 test riêng của bốn module và toàn bộ 79 test xanh; chạy calibration, pipeline, xem mẫu ảnh và thử gate với budget 0. `check-core` ban đầu quét nhầm file khóa do dấu phân cách đường dẫn Windows; chuẩn hóa đường dẫn sang POSIX giữ nguyên kiểm soát, sau đó checker báo 0 lỗi (1 cảnh báo vì chưa train).
- Lỗi AI đã sửa: bản đầu có thể ghi `needs_label` cho ảnh đồng thời bị xóa; rà lại ca biên đã giúp bỏ hành động thừa này trước lần kiểm cuối.

Train Colab và phần thưởng CVAT chưa làm; có thể bổ sung sau nếu cần các điểm tùy chọn.
