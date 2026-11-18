"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


def run(ds, cfg, preds=None):
    """So nhãn với dự đoán model cache; chỉ tạo cảnh báo để người xem xét."""
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    rules = cfg["second_opinion"]
    issues = []
    for image_path in ds.image_files():
        stem = image_path.stem
        if stem not in preds or not ds.label_path(stem).exists():
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        image_width, image_height = size

        # Retain source line numbers while matching the same valid rows as Dataset.valid_boxes.
        labels = []
        for line_no, raw in ds.read_label_lines(stem) or []:
            try:
                box = parse_yolo_line(raw)
            except (ValueError, OverflowError):
                continue
            if not 0 <= box[0] < len(ds.classes):
                continue
            labels.append((line_no, box[0], tuple(box[1:])))

        parsed_preds = []
        for raw_pred in preds.get(stem, []):
            try:
                cls, conf, cx, cy, width, height = raw_pred
                pred = (int(cls), float(conf), float(cx), float(cy), float(width), float(height))
            except (TypeError, ValueError, OverflowError):
                continue
            if not all(value == value and abs(value) != float("inf") for value in pred):
                continue
            parsed_preds.append(pred)

        checked_preds = [
            pred for pred in parsed_preds
            if pred[1] >= rules["conf"]
            and pred[4] * image_width * pred[5] * image_height >= rules["min_area_px"]
        ]
        all_for_false_positive = [pred for pred in parsed_preds if pred[1] >= rules["fp_conf"]]

        # Report model-first disagreements in prediction order.
        for cls, conf, cx, cy, width, height in checked_preds:
            pred_box = (cx, cy, width, height)
            candidates = [
                (label_cls, label_box, iou_xywh(pred_box, label_box))
                for _, label_cls, label_box in labels
                if iou_xywh(pred_box, label_box) >= rules["iou_missing"]
            ]
            if not candidates:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_MISSING", stem,
                                    "Model thấy vật chưa có box nhãn tương ứng", extra={"conf": conf}))
                continue

            same_class = [item for item in candidates if item[0] == cls]
            if same_class:
                best_iou = max(item[2] for item in same_class)
                if best_iou < rules["iou_loose"]:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_LOOSE_BOX", stem,
                                        "Box cùng lớp có thể lỏng hoặc lệch so với dự đoán", extra={"conf": conf, "iou": best_iou}))
                continue

            other_class = [item for item in candidates if item[0] != cls]
            if other_class:
                best_iou = max(item[2] for item in other_class)
                if best_iou >= rules["iou_match"]:
                    issues.append(Issue("second_opinion", WARN, "POSSIBLE_WRONG_CLASS", stem,
                                        "Model và nhãn có thể bất đồng về lớp", extra={"conf": conf, "iou": best_iou}))

        # Label-first disagreements use fp_conf and deliberately have no area filter.
        for line_no, _, label_box in labels:
            best_iou = max((iou_xywh(label_box, pred[2:]) for pred in all_for_false_positive), default=0.0)
            if best_iou < rules["iou_missing"]:
                issues.append(Issue("second_opinion", WARN, "POSSIBLE_FALSE_POS", stem,
                                    "Box nhãn không khớp dự đoán nào của model", line_no,
                                    {"iou": best_iou}))

    return issues
