import cv2
import numpy as np


def check_ppe_hsv_fallback(frame, person_box):
    """HSV fallback for gear classes not present in the loaded deep-learning PPE weights."""
    px1, py1, px2, py2 = person_box
    h_img, w_img = frame.shape[:2]
    px1, py1 = max(0, px1), max(0, py1)
    px2, py2 = min(w_img, px2), min(h_img, py2)

    p_w = max(1, px2 - px1)
    p_h = max(1, py2 - py1)
    person_crop = frame[py1:py2, px1:px2]
    if person_crop.size == 0 or p_h < 40 or p_w < 15:
        return False, False, False

    hsv_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)

    # 1. Helmet (Top 28%)
    head_h = max(1, int(p_h * 0.28))
    head_hsv = hsv_crop[0:head_h, :]
    m_yellow = cv2.inRange(head_hsv, np.array([18, 75, 85]), np.array([42, 255, 255]))
    m_white = cv2.inRange(head_hsv, np.array([0, 0, 165]), np.array([180, 55, 255]))
    m_blue = cv2.inRange(head_hsv, np.array([95, 90, 70]), np.array([130, 255, 255]))
    m_red1 = cv2.inRange(head_hsv, np.array([0, 100, 80]), np.array([12, 255, 255]))
    m_red2 = cv2.inRange(head_hsv, np.array([168, 100, 80]), np.array([180, 255, 255]))
    hat_px = (
        cv2.countNonZero(m_yellow)
        + cv2.countNonZero(m_white)
        + cv2.countNonZero(m_blue)
        + cv2.countNonZero(m_red1)
        + cv2.countNonZero(m_red2)
    )
    has_helmet = (hat_px / float(head_h * p_w)) >= 0.06

    # 2. High-Vis Vest / Orange High-Vis Workwear (Torso 18% - 68%)
    torso_y1 = int(p_h * 0.18)
    torso_y2 = max(torso_y1 + 1, int(p_h * 0.68))
    torso_hsv = hsv_crop[torso_y1:torso_y2, :]
    m_neon = cv2.inRange(torso_hsv, np.array([20, 40, 65]), np.array([75, 255, 255]))
    m_orange = cv2.inRange(torso_hsv, np.array([4, 70, 70]), np.array([22, 255, 255]))
    m_silver = cv2.inRange(torso_hsv, np.array([0, 0, 185]), np.array([180, 50, 255]))
    vest_px = cv2.countNonZero(m_neon) + cv2.countNonZero(m_orange) + cv2.countNonZero(m_silver)
    has_vest = (vest_px / float((torso_y2 - torso_y1) * p_w)) >= 0.06

    # 3. Boots (Bottom 28%)
    feet_y1 = int(p_h * 0.72)
    feet_hsv = hsv_crop[feet_y1:, :]
    total_feet_px = max(1, (p_h - feet_y1) * p_w)
    m_dark_boot = cv2.inRange(feet_hsv, np.array([0, 0, 10]), np.array([180, 150, 90]))
    m_yellow_boot = cv2.inRange(feet_hsv, np.array([18, 70, 70]), np.array([42, 255, 255]))
    boot_px = cv2.countNonZero(m_dark_boot) + cv2.countNonZero(m_yellow_boot)
    has_boot = (boot_px / float(total_feet_px)) >= 0.10

    return has_helmet, has_vest, has_boot


def box_containment_ratio(inner_box, outer_box):
    ix1, iy1, ix2, iy2 = inner_box
    ox1, oy1, ox2, oy2 = outer_box

    inter_x1 = max(ix1, ox1)
    inter_y1 = max(iy1, oy1)
    inter_x2 = min(ix2, ox2)
    inter_y2 = min(iy2, oy2)

    if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
        return 0.0

    inter_area = float((inter_x2 - inter_x1) * (inter_y2 - inter_y1))
    inner_area = max(1.0, float((ix2 - ix1) * (iy2 - iy1)))
    return inter_area / inner_area


def is_inside_roi(person_box, roi_polygon, frame_w, frame_h):
    if not roi_polygon or len(roi_polygon) < 3:
        return True

    px1, py1, px2, py2 = person_box
    foot_x = (px1 + px2) / 2.0
    foot_y = float(py2)

    pts = []
    for pt in roi_polygon:
        x, y = pt[0], pt[1]
        if isinstance(x, float) and x <= 1.0 and isinstance(y, float) and y <= 1.0:
            pts.append([int(x * frame_w), int(y * frame_h)])
        else:
            pts.append([int(x), int(y)])

    poly = np.array(pts, dtype=np.int32)
    return cv2.pointPolygonTest(poly, (float(foot_x), float(foot_y)), measureDist=False) >= 0


class PersonSafetyTracker:
    """Fuses primary person detections with deep-learning PPE detections + smart per-class fallback."""

    def __init__(self, containment_threshold=0.40):
        self.containment_thresh = containment_threshold

    def evaluate_frame(self, detections, raw_frame=None, roi_polygon=None):
        persons = []
        ppe_items = []
        hazards = []

        if isinstance(detections, list):
            for d in detections:
                lbl = d.get("label", "").lower()
                if lbl in ["person", "worker"]:
                    persons.append(d)
                elif lbl in ["helmet", "no_helmet", "vest", "no_vest", "boot", "no_shoes"]:
                    ppe_items.append(d)
                elif lbl in ["fire", "smoke"]:
                    hazards.append(d)

        frame_h, frame_w = (raw_frame.shape[:2]) if raw_frame is not None else (1080, 1920)
        has_dl_helmet = any(item["label"] in ["helmet", "no_helmet"] for item in ppe_items)
        has_dl_vest = any(item["label"] in ["vest", "no_vest"] for item in ppe_items)
        has_dl_boot = any(item["label"] in ["boot", "no_shoes"] for item in ppe_items)

        evaluated_workers = []
        for p in persons:
            p_box = [int(v) for v in p["bbox"]]
            px1, py1, px2, py2 = p_box
            p_w = max(1, px2 - px1)
            p_h = max(1, py2 - py1)

            if p_h < 65 or p_w < 22:
                continue

            if roi_polygon and not is_inside_roi(p_box, roi_polygon, frame_w, frame_h):
                continue

            aspect_ratio = p_h / float(p_w)
            is_lower_body_occluded = aspect_ratio < 1.6

            hsv_helmet, hsv_vest, hsv_boot = (False, False, True)
            if raw_frame is not None:
                hsv_helmet, hsv_vest, hsv_boot = check_ppe_hsv_fallback(raw_frame, p_box)

            expanded_person = [
                max(0, px1 - int(p_w * 0.12)),
                max(0, py1 - int(p_h * 0.15)),
                min(frame_w, px2 + int(p_w * 0.12)),
                py2,
            ]
            head_cutoff_y = py1 + int(p_h * 0.45)

            helmet_conf = 0.0
            no_helmet_conf = 0.0
            vest_conf = 0.0
            no_vest_conf = 0.0
            boot_conf = 0.0
            no_boot_conf = 0.0

            for item in ppe_items:
                ibox = item["bbox"]
                lbl = item["label"]
                conf = item.get("confidence", 0.0)
                iy_center = (ibox[1] + ibox[3]) / 2.0

                if box_containment_ratio(ibox, expanded_person) < self.containment_thresh:
                    continue

                if lbl == "helmet" and iy_center <= head_cutoff_y:
                    helmet_conf = max(helmet_conf, conf)
                elif lbl == "no_helmet" and iy_center <= head_cutoff_y:
                    no_helmet_conf = max(no_helmet_conf, conf)
                elif lbl == "vest":
                    vest_conf = max(vest_conf, conf)
                elif lbl == "no_vest":
                    no_vest_conf = max(no_vest_conf, conf)
                elif lbl == "boot":
                    boot_conf = max(boot_conf, conf)
                elif lbl == "no_shoes":
                    no_boot_conf = max(no_boot_conf, conf)

            # Use Deep Learning when detected for that gear type, otherwise fall back to HSV
            if has_dl_helmet:
                has_helmet = (helmet_conf > 0.0) and (helmet_conf >= no_helmet_conf)
            else:
                has_helmet = hsv_helmet

            if has_dl_vest:
                has_vest = (vest_conf > 0.0) and (vest_conf >= no_vest_conf)
            else:
                has_vest = hsv_vest

            if has_dl_boot:
                has_boot = (boot_conf > 0.0) and (boot_conf >= no_boot_conf)
            else:
                has_boot = hsv_boot

            missing = []
            if not has_helmet:
                missing.append("helmet")
            if not has_vest:
                missing.append("vest")
            if not has_boot and not is_lower_body_occluded:
                missing.append("boot")

            evaluated_workers.append({
                "person_bbox": p_box,
                "confidence": p.get("confidence", 0.0),
                "has_helmet": has_helmet,
                "has_vest": has_vest,
                "has_boot": has_boot,
                "missing_gear": missing,
                "compliant": len(missing) == 0,
            })

        return evaluated_workers, hazards
