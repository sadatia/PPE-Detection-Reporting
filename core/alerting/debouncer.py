import time
import logging

class ViolationDebouncer:
    """
    Prevents alert spam by:
    1. Grouping multiple missing PPE items into a single combined alert.
    2. Enforcing a persistent violation threshold (default 3.0s).
    3. Applying a camera-wide cooldown (default 120s) so identical locations 
       do not trigger rapid-fire notifications.
    """
    def __init__(self, ppe_persist=3.0, fire_persist=1.0, cooldown_seconds=120.0):
        self.ppe_persist = float(ppe_persist)
        self.fire_persist = float(fire_persist)
        self.cooldown = float(cooldown_seconds)

        # Persistence tracker: {cam_id: first_seen_time}
        self.cam_violation_start = {}
        # Cooldown tracker: {cam_id: last_alert_time}
        self.cam_last_alert = {}

    def process_events(self, cam_id, workers, hazards):
        now = time.perf_counter()
        alerts_to_fire = []

        # 1. Check Hazards (Fire / Smoke) - High Priority
        hazard_types = sorted(list(set(h["label"].lower() for h in hazards if h["label"].lower() in ["fire", "smoke"])))
        if hazard_types:
            state_key = f"{cam_id}_hazard"
            if state_key not in self.cam_violation_start:
                self.cam_violation_start[state_key] = now
            elif (now - self.cam_violation_start[state_key]) >= self.fire_persist:
                last_alert = self.cam_last_alert.get(state_key, 0.0)
                if (now - last_alert) >= self.cooldown:
                    alerts_to_fire.append({
                        "cam_id": cam_id,
                        "type": " & ".join(hazard_types).upper(),
                        "severity": "CRITICAL",
                        "duration": round(now - self.cam_violation_start[state_key], 1)
                    })
                    self.cam_last_alert[state_key] = now
            return alerts_to_fire
        else:
            self.cam_violation_start.pop(f"{cam_id}_hazard", None)

        # 2. Check PPE Violations (Consolidated)
        all_missing = set()
        total_violators = 0
        for w in workers:
            missing = w.get("missing_gear", [])
            if missing:
                total_violators += 1
                for item in missing:
                    all_missing.add(item)

        if all_missing:
            state_key = f"{cam_id}_ppe"
            if state_key not in self.cam_violation_start:
                self.cam_violation_start[state_key] = now
            elif (now - self.cam_violation_start[state_key]) >= self.ppe_persist:
                last_alert = self.cam_last_alert.get(state_key, 0.0)
                # Enforce camera-level cooldown
                if (now - last_alert) >= self.cooldown:
                    # Create one single consolidated label e.g., "MISSING: HELMET, VEST, BOOT"
                    formatted_items = ", ".join(sorted(list(all_missing))).upper()
                    alerts_to_fire.append({
                        "cam_id": cam_id,
                        "type": f"MISSING PPE: {formatted_items}",
                        "raw_type": "missing_ppe",
                        "severity": "WARNING",
                        "worker_count": total_violators,
                        "duration": round(now - self.cam_violation_start[state_key], 1)
                    })
                    self.cam_last_alert[state_key] = now
        else:
            self.cam_violation_start.pop(f"{cam_id}_ppe", None)

        return alerts_to_fire
