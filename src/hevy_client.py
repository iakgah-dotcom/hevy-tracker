"""Hevy API client — fetches workout data."""
import time
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone, timedelta
from typing import Any


BASE_URL = "https://api.hevyapp.com/v1"
PAGE_SIZE = 10

# BIG3 exercise template IDs (barbell = primary, others = variants)
BIG3_TEMPLATES = {
    "bench": {
        "primary": "79D0BB3A",  # Bench Press (Barbell)
        "variants": ["3601968B", "0FBF7195", "E644F828", "35B51B87", "867AC3B6"],
    },
    "deadlift": {
        "primary": "C6272009",  # Deadlift (Barbell)
        "variants": ["B923B230", "D20D7BBE", "2A48E443", "FA5D0DE1"],
    },
    "squat": {
        "primary": "D04AC939",  # Squat (Barbell)
        "variants": ["DDCC3821", "38FC1AB9", "5046D0A9", "CE1054CE", "1283BBA6"],
    },
}

BIG3_LABELS = {
    "bench": "ベンチプレス",
    "deadlift": "デッドリフト",
    "squat": "スクワット",
}

# Reverse lookup: template_id -> (lift_name, is_primary)
TEMPLATE_LOOKUP: dict[str, tuple[str, bool]] = {}
for _lift, _data in BIG3_TEMPLATES.items():
    TEMPLATE_LOOKUP[_data["primary"]] = (_lift, True)
    for _v in _data["variants"]:
        TEMPLATE_LOOKUP[_v] = (_lift, False)


# 種目別 1RM 推定式
# bench:           weight × reps / 40   + weight
# squat/deadlift:  weight × reps / 33.3 + weight
_E1RM_DIVISOR = {"bench": 40.0, "deadlift": 33.3, "squat": 33.3}


def _calc_e1rm(lift: str, weight: float, reps: int) -> float:
    divisor = _E1RM_DIVISOR[lift]
    return weight * reps / divisor + weight


class HevyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{BASE_URL}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"
        req = urllib.request.Request(url, headers={"api-key": self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Hevy API error {e.code}: {e.reason}") from e

    def get_all_workouts(self) -> list[dict]:
        """Fetch every workout, newest first."""
        workouts: list[dict] = []
        page = 1
        while True:
            data = self._get("/workouts", {"page": page, "pageSize": PAGE_SIZE})
            workouts.extend(data["workouts"])
            if page >= data["page_count"]:
                break
            page += 1
            time.sleep(0.3)  # be polite to the API
        return workouts

    def get_workouts_since(self, since: datetime) -> list[dict]:
        """Return workouts that started on or after `since` (UTC-aware)."""
        all_wk = self.get_all_workouts()
        result = []
        for w in all_wk:
            start = datetime.fromisoformat(w["start_time"].replace("Z", "+00:00"))
            if start >= since:
                result.append(w)
        return result

    def get_big3_sets(self, workouts: list[dict]) -> list[dict]:
        """
        Extract every set that belongs to a BIG3 exercise.
        Returns a flat list of set records with enriched metadata.
        """
        records: list[dict] = []
        for w in workouts:
            start = datetime.fromisoformat(w["start_time"].replace("Z", "+00:00"))
            jst = timezone(timedelta(hours=9))
            start_jst = start.astimezone(jst)
            for ex in w["exercises"]:
                tid = ex.get("exercise_template_id", "")
                if tid not in TEMPLATE_LOOKUP:
                    continue
                lift, is_primary = TEMPLATE_LOOKUP[tid]
                for s in ex["sets"]:
                    if s["type"] != "normal":
                        continue
                    kg = s.get("weight_kg") or 0
                    reps = s.get("reps") or 0
                    if kg <= 0 or reps <= 0:
                        continue
                    records.append({
                        "workout_id": w["id"],
                        "date": start_jst.date(),
                        "week": start_jst.isocalendar()[1],
                        "year": start_jst.year,
                        "lift": lift,
                        "label": BIG3_LABELS[lift],
                        "exercise_name": ex["title"].strip(),
                        "is_primary": is_primary,
                        "weight_kg": kg,
                        "reps": reps,
                        "volume": kg * reps,
                        "e1rm": round(_calc_e1rm(lift, kg, reps), 1),
                    })
        return records
