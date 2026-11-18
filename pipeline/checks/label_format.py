"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    """Kiểm tra cú pháp và hình học của từng dòng nhãn YOLO."""
    issues = []
    rules = cfg["label_format"]
    n_classes = len(ds.classes)

    for path in ds.label_files():
        stem = path.stem
        lines = ds.read_label_lines(stem) or []
        size = ds.image_size(stem)
        seen_by_class = {}

        for line_no, raw in lines:
            try:
                cls, cx, cy, width, height = parse_yolo_line(raw)
            except (ValueError, OverflowError) as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    f"Dòng nhãn không hợp lệ: {exc}", line_no))
                continue

            if not 0 <= cls < n_classes:
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"ID lớp {cls} không nằm trong 0..{n_classes - 1}", line_no))
                continue

            if width <= 0 or height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "Chiều rộng và chiều cao box phải lớn hơn 0", line_no))
                continue

            left, top = cx - width / 2, cy - height / 2
            right, bottom = cx + width / 2, cy + height / 2
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
            if overflow > rules["overflow_tol"]:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"Box tràn ảnh {overflow:.6g}", line_no,
                                    {"overflow": overflow}))

            box = (cx, cy, width, height)
            previous = seen_by_class.setdefault(cls, [])
            if any(iou_xywh(box, old_box) > rules["dup_box_iou"] for old_box in previous):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                    "Box trùng với một dòng trước cùng lớp", line_no))
            previous.append(box)

            if size is not None:
                image_width, image_height = size
                short_side_px = min(width * image_width, height * image_height)
                if short_side_px < rules["min_box_px"]:
                    issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                        f"Cạnh ngắn của box chỉ {short_side_px:.2f}px", line_no))

            if width * height > rules["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    f"Box chiếm {width * height:.4f} diện tích chuẩn hóa", line_no))

    return issues
