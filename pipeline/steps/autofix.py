"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    """Sửa các lỗi ERROR có quy tắc an toàn và ghi lại từng thay đổi."""
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    line_actions = defaultdict(dict)
    remove_images = set()
    needs_labels = set()
    rename_classes = False

    for issue in issues:
        if issue.severity != ERROR:
            continue
        if issue.code in remove_codes:
            remove_images.add(issue.image)
        elif issue.code == "MISSING_LABEL_FILE":
            needs_labels.add(issue.image)
        elif issue.code == "BAD_CLASS_NAME":
            rename_classes = True
        elif issue.code in drop_codes and issue.line is not None:
            line_actions[issue.image].setdefault(issue.line, set()).add(issue.code)
        elif issue.code == "BOX_OUT_OF_IMAGE" and issue.line is not None:
            line_actions[issue.image].setdefault(issue.line, set()).add(issue.code)

    changes = []

    # Log each image-level action once, even if duplicate issues refer to it.
    for stem in sorted(remove_images):
        removed_any = False
        for path in ds.image_files():
            if path.stem == stem:
                path.unlink(missing_ok=True)
                removed_any = True
        label_path = ds.label_path(stem)
        if label_path.exists():
            label_path.unlink()
            removed_any = True
        if removed_any:
            changes.append({"image": stem, "line": "", "action": "remove_image",
                            "before": "ảnh và nhãn trong dataset", "after": "đã loại khỏi dataset"})

    for stem in sorted(needs_labels):
        # A missing annotation cannot be safely inferred by this deterministic fixer.
        if stem not in remove_images and not ds.label_path(stem).exists():
            changes.append({"image": stem, "line": "", "action": "needs_label",
                            "before": "(không có file)", "after": "chuyển người gán"})

    if rename_classes and ds.yaml_path.exists():
        data = yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            data = {}
        before_names = data.get("names", "")
        data["names"] = list(cfg["classes"])
        ds.yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
        changes.append({"image": "data.yaml", "line": "", "action": "rename_classes",
                        "before": str(before_names), "after": str(cfg["classes"])})

    # Process each label file once so original line numbers stay meaningful.
    for stem in sorted(line_actions):
        if stem in remove_images:
            continue
        path = ds.label_path(stem)
        if not path.exists():
            continue
        original_text = path.read_text(encoding="utf-8", errors="replace")
        original_lines = original_text.splitlines()
        output_lines = []
        file_changes = []

        for line_no, raw in enumerate(original_lines, start=1):
            codes = line_actions[stem].get(line_no)
            if not codes:
                output_lines.append(raw)
                continue

            if codes & drop_codes:
                file_changes.append({"image": stem, "line": line_no, "action": "drop_line",
                                     "before": raw, "after": "(đã xóa)"})
                continue

            if "BOX_OUT_OF_IMAGE" in codes:
                try:
                    cls, cx, cy, width, height = parse_yolo_line(raw)
                except (ValueError, OverflowError):
                    # The format checker owns malformed lines; do not guess at them.
                    output_lines.append(raw)
                    continue
                x1, x2 = max(0.0, cx - width / 2), min(1.0, cx + width / 2)
                y1, y2 = max(0.0, cy - height / 2), min(1.0, cy + height / 2)
                if x2 <= x1 or y2 <= y1:
                    file_changes.append({"image": stem, "line": line_no, "action": "drop_line",
                                         "before": raw, "after": "(đã xóa: box không giao ảnh)"})
                    continue
                clipped = (cls, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)
                after = " ".join([str(clipped[0]), *(format(value, ".10g") for value in clipped[1:])])
                output_lines.append(after)
                if after != raw:
                    file_changes.append({"image": stem, "line": line_no, "action": "clip_box",
                                         "before": raw, "after": after})
                continue

            output_lines.append(raw)

        if output_lines != original_lines:
            ending = "\n" if original_text.endswith(("\n", "\r")) else ""
            path.write_text("\n".join(output_lines) + ending, encoding="utf-8")
        changes.extend(file_changes)

    return changes
