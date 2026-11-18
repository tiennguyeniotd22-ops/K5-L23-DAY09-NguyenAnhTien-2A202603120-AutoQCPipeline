"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    """Áp dụng thứ tự ưu tiên Rework, Hold, Release theo quy tắc dự án."""
    stems = set(image_stems)
    reviewed = set(reviewed or ())
    errors = [issue for issue in issues if issue.severity == ERROR]
    warn_images = {
        issue.image for issue in issues
        if issue.severity == WARN and issue.image in stems and issue.image not in reviewed
    }
    n_images = len(stems)
    n_errors = len(errors)
    n_warn_images = len(warn_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0
    rounded_ratio = round(warn_ratio, 4)

    if n_errors:
        decision = "Rework"
        reasons = [f"Còn {n_errors} lỗi bắt buộc (ERROR), cần sửa trước khi phát hành."]
    elif warn_ratio >= cfg["gate"]["warn_ratio_hold"]:
        decision = "Hold"
        reasons = [
            f"{n_warn_images}/{n_images} ảnh còn cảnh báo chưa duyệt "
            f"({rounded_ratio:.1%}), đạt/vượt ngưỡng Hold "
            f"{cfg['gate']['warn_ratio_hold']:.1%}."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; {n_warn_images}/{n_images} ảnh còn cảnh báo "
            f"({rounded_ratio:.1%}), dưới ngưỡng Hold {cfg['gate']['warn_ratio_hold']:.1%}."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": rounded_ratio,
        "reasons": reasons,
    }
