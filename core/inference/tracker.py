import cv2
import numpy as np

def check_ppe_heuristics(frame, person_box):
    """
    Analyzes anatomical regions of a detected worker box using HSV color 
    and edge density to identify safety helmet, high-vis vest, and boots.
    """
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

    # 1. Hardhat / Helmet (Top 30%)
    head_h = int(p_h * 0.30)
    head_hsv = hsv_crop[0:head_h, :]
    
    m_yellow_hat = cv2.inRange(head_hsv, np.array([20, 80, 90]), np.array([40, 255, 255]))
    m_white_hat = cv2.inRange(head_hsv, np.array([0, 0, 170]), np.array([180, 45, 255]))
    m_blue_hat = cv2.inRange(head_hsv, np.array([95, 100, 70]), np.array([130, 255, 255]))
    m_red_hat1 = cv2.inRange(head_hsv, np.array([0, 110, 80]), np.array([10, 255, 255]))
    m_red_hat2 = cv2.inRange(head_hsv, np.array([170, 110, 80]), np.array([180, 255, 255]))
    
    total_head_px = max(1, head_h * p_w)
    hat_px = (cv2.countNonZero(m_yellow_hat) + 
              cv2.countNonZero(m_white_hat) + 
              cv2.countNonZero(m_blue_hat) + 
              cv2.countNonZero(m_red_hat1) + 
              cv2.countNonZero(m_red_hat2))
    
    has_helmet = (hat_px / float(total_head_px)) >= 0.08

    # 2. Safety Vest (Torso 15% - 75%)
    torso_y1 = int(p_h * 0.15)
    torso_y2 = int(p_h * 0.75)
    torso_hsv = hsv_crop[torso_y1:torso_y2, :]

    # Neon yellow/lime (lower saturation limit to 35 for nighttime glare)
    m_neon_vest = cv2.inRange(torso_hsv, np.array([20, 35, 60]), np.array([75, 255, 255]))
    # Hi-vis orange/red
    m_orange_vest = cv2.inRange(torso_hsv, np.array([5, 60, 60]), np.array([24, 255, 255]))
    # Retro-reflective silver/white strips under floodlights
    m_silver_tape = cv2.inRange(torso_hsv, np.array([0, 0, 190]), np.array([180, 50, 255]))

    total_torso_px = max(1, (torso_y2 - torso_y1) * p_w)
    vest_px = cv2.countNonZero(m_neon_vest) + cv2.countNonZero(m_orange_vest) + cv2.countNonZero(m_silver_tape)
    has_vest = (vest_px / float(total_torso_px)) >= 0.07

    # 3. Boots (Bottom 30%)
    feet_y1 = int(p_h * 0.70)
    feet_hsv = hsv_crop[feet_y1:, :]
    total_feet_px = max(1, (p_h - feet_y1) * p_w)

    m_dark_boot = cv2.inRange(feet_hsv, np.array([0, 0, 10]), np.array([180, 150, 85]))
    m_yellow_boot = cv2.inRange(feet_hsv, np.array([20, 70, 70]), np.array([40, 255, 255]))
    boot_px = cv2.countNonZero(m_dark_boot) + cv2.countNonZero(m_yellow_boot)
    
    has_boot = (boot_px / float(total_feet_px)) >= 0.12

    return has_helmet, has_vest, has_boot


def is_inside_roi(person_box, roi_polygon, frame_w, frame_h):
    """
    Checks if a person's ground foot contact point is inside the ROI polygon.
    roi_polygon can be normalized [0.0 - 1.0] or raw pixel coordinates.
    """
    if not roi_polygon or len(roi_polygon) < 3:
        return True  # No ROI defined = full frame monitored

    px1, py1, px2, py2 = person_box
    # Check bottom-center of the person (where they are standing)
    foot_x = (px1 + px2) / 2.0
    foot_y = float(py2)

    # Convert normalized polygon coordinates to pixel coordinates
    pts = []
    for pt in roi_polygon:
        x, y = pt[0], pt[1]
        if isinstance(x, float) and x <= 1.0 and isinstance(y, float) and y <= 1.0:
            pts.append([int(x * frame_w), int(y * frame_h)])
        else:
            pts.append([int(x), int(y)])
            
    poly = np.array(pts, dtype=np.int32)
    # pointPolygonTest returns >= 0 if inside or on edge
    result = cv2.pointPolygonTest(poly, (float(foot_x), float(foot_y)), measureDist=False)
    return result >= 0


class PersonSafetyTracker:
    """Evaluates worker compliance within active ROI monitored zones."""

    def __init__(self, containment_threshold=0.15):
        self.containment_thresh = containment_threshold

    def evaluate_frame(self, detections, raw_frame=None, roi_polygon=None):
        persons = []
        hazards = []

        if isinstance(detections, list):
            for d in detections:
                lbl = d.get("label", "").lower()
                if lbl in ["person", "worker"]:
                    persons.append(d)
                elif lbl in ["fire", "smoke"]:
                    hazards.append(d)

        frame_h, frame_w = (raw_frame.shape[:2]) if raw_frame is not None else (1080, 1920)

        evaluated_workers = []
        for p in persons:
            p_box = [int(v) for v in p["bbox"]]
            px1, py1, px2, py2 = p_box
            p_w = max(1, px2 - px1)
            p_h = max(1, py2 - py1)

            # Skip distant / blurry workers
            if p_h < 115 or p_w < 35:
                continue

            # ROI CHECK: Ignore workers outside the selected monitoring zone
            if roi_polygon and not is_inside_roi(p_box, roi_polygon, frame_w, frame_h):
                continue

            aspect_ratio = p_h / float(p_w)
            is_lower_body_occluded = aspect_ratio < 1.6

            has_helmet, has_vest, has_boot = False, False, False
            if raw_frame is not None:
                has_helmet, has_vest, has_boot = check_ppe_heuristics(raw_frame, p_box)

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
                "compliant": len(missing) == 0
            })

        return evaluated_workers, hazards
