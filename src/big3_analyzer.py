"""BIG3 weekly analysis — computes metrics and generates training recommendations."""
from collections import defaultdict
from datetime import date, timedelta
from typing import Any


LIFT_ORDER = ["bench", "deadlift", "squat"]
LIFT_LABELS = {"bench": "ベンチプレス", "deadlift": "デッドリフト", "squat": "スクワット"}


def _week_key(year: int, week: int) -> str:
    return f"{year}-W{week:02d}"


def aggregate_by_week(records: list[dict]) -> dict[str, dict[str, dict]]:
    """
    Returns: {lift: {week_key: {max_e1rm, max_weight, total_volume, sessions, sets}}}
    """
    data: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "max_e1rm": 0.0,
        "max_weight": 0.0,
        "total_volume": 0.0,
        "sessions": set(),
        "sets": 0,
        "best_set": None,
    }))

    for r in records:
        wk = _week_key(r["year"], r["week"])
        entry = data[r["lift"]][wk]
        if r["e1rm"] > entry["max_e1rm"]:
            entry["max_e1rm"] = r["e1rm"]
            entry["best_set"] = r
        entry["max_weight"] = max(entry["max_weight"], r["weight_kg"])
        entry["total_volume"] += r["volume"]
        entry["sessions"].add(r["workout_id"])
        entry["sets"] += 1

    # convert sets to counts
    for lift in data:
        for wk in data[lift]:
            data[lift][wk]["sessions"] = len(data[lift][wk]["sessions"])

    return data


def get_current_and_prev_week(records: list[dict]) -> tuple[str, str]:
    """Return (current_week_key, prev_week_key) based on record dates."""
    if not records:
        today = date.today()
        iso = today.isocalendar()
        curr = _week_key(iso[0], iso[1])
        prev_day = today - timedelta(weeks=1)
        iso2 = prev_day.isocalendar()
        prev = _week_key(iso2[0], iso2[1])
        return curr, prev

    dates = sorted({r["date"] for r in records}, reverse=True)
    latest = dates[0]
    iso = latest.isocalendar()
    curr = _week_key(iso[0], iso[1])
    prev_day = latest - timedelta(weeks=1)
    iso2 = prev_day.isocalendar()
    prev = _week_key(iso2[0], iso2[1])
    return curr, prev


def analyze_week(records: list[dict], week_key: str) -> dict[str, Any]:
    """
    Full analysis for a single week.
    Returns per-lift metrics and overall summary.
    """
    weekly = aggregate_by_week(records)
    result: dict[str, Any] = {"week": week_key, "lifts": {}}

    for lift in LIFT_ORDER:
        entry = weekly.get(lift, {}).get(week_key)
        if entry:
            result["lifts"][lift] = {
                "label": LIFT_LABELS[lift],
                "max_e1rm": entry["max_e1rm"],
                "max_weight": entry["max_weight"],
                "total_volume": entry["total_volume"],
                "sessions": entry["sessions"],
                "sets": entry["sets"],
                "best_set": entry["best_set"],
            }
        else:
            result["lifts"][lift] = None

    return result


def compare_weeks(records: list[dict], curr_key: str, prev_key: str) -> dict[str, Any]:
    """Diff between current and previous week."""
    weekly = aggregate_by_week(records)
    comparison: dict[str, Any] = {}

    for lift in LIFT_ORDER:
        curr = weekly.get(lift, {}).get(curr_key)
        prev = weekly.get(lift, {}).get(prev_key)

        if curr is None and prev is None:
            comparison[lift] = None
            continue

        curr_e1rm = curr["max_e1rm"] if curr else 0
        prev_e1rm = prev["max_e1rm"] if prev else 0
        curr_vol = curr["total_volume"] if curr else 0
        prev_vol = prev["total_volume"] if prev else 0

        e1rm_diff = curr_e1rm - prev_e1rm
        e1rm_pct = (e1rm_diff / prev_e1rm * 100) if prev_e1rm else None
        vol_diff = curr_vol - prev_vol
        vol_pct = (vol_diff / prev_vol * 100) if prev_vol else None

        comparison[lift] = {
            "label": LIFT_LABELS[lift],
            "curr_e1rm": curr_e1rm,
            "prev_e1rm": prev_e1rm,
            "e1rm_diff": e1rm_diff,
            "e1rm_pct": e1rm_pct,
            "curr_volume": curr_vol,
            "prev_volume": prev_vol,
            "vol_diff": vol_diff,
            "vol_pct": vol_pct,
            "trend": _trend(e1rm_diff),
        }

    return comparison


def _trend(diff: float) -> str:
    if diff > 2.5:
        return "↑ 上昇"
    if diff < -2.5:
        return "↓ 下降"
    return "→ 維持"


def generate_menu_suggestions(comparison: dict[str, Any]) -> list[str]:
    """
    Generate next-week training menu suggestions based on current week performance.
    """
    suggestions: list[str] = []

    for lift in LIFT_ORDER:
        data = comparison.get(lift)
        label = LIFT_LABELS[lift]

        if data is None:
            suggestions.append(
                f"【{label}】今週のデータなし → 来週は必ず実施しましょう。"
            )
            continue

        e1rm = data["curr_e1rm"]
        diff = data["e1rm_diff"]
        pct = data["e1rm_pct"]

        if diff > 5:
            suggestions.append(
                f"【{label}】大きな進歩（推定1RM +{diff:.1f}kg）！"
                f" 来週は同重量×セット数増加 or +2.5kg にチャレンジ。"
            )
        elif diff > 0:
            suggestions.append(
                f"【{label}】順調な伸び（+{diff:.1f}kg）。"
                f" 来週は同重量でRPE8程度を目標にしましょう。"
            )
        elif diff < -5:
            suggestions.append(
                f"【{label}】パフォーマンス低下（{diff:.1f}kg）。"
                f" 疲労蓄積の可能性あり。来週はデロード週（70%強度）を推奨。"
            )
        else:
            suggestions.append(
                f"【{label}】ほぼ横ばい（{diff:+.1f}kg）。"
                f" フォームの質とRPEに集中して同重量を継続。"
            )

        # volume guidance
        vol = data["curr_volume"]
        if vol < 3000:
            suggestions.append(f"  → ボリューム不足（{vol:.0f}kg）。セット数を増やしてください。")
        elif vol > 15000:
            suggestions.append(f"  → ボリューム過多（{vol:.0f}kg）の可能性。回復を優先。")

    # general
    suggestions.append("")
    suggestions.append("【共通アドバイス】")
    suggestions.append("・BIG3は週2回以上の頻度が筋力向上に効果的です。")
    suggestions.append("・睡眠7〜9時間・たんぱく質体重×2g/日を確保しましょう。")
    suggestions.append("・フォームが崩れる重量では無理に記録更新しないこと。")

    return suggestions


def all_time_prs(records: list[dict]) -> dict[str, dict]:
    """Compute all-time PR (max e1rm and max weight) per lift."""
    prs: dict[str, dict] = {}
    for lift in LIFT_ORDER:
        lift_records = [r for r in records if r["lift"] == lift]
        if not lift_records:
            prs[lift] = {"label": LIFT_LABELS[lift], "max_e1rm": 0, "max_weight": 0, "best_set": None}
            continue
        best_e1rm = max(lift_records, key=lambda r: r["e1rm"])
        best_weight = max(lift_records, key=lambda r: r["weight_kg"])
        prs[lift] = {
            "label": LIFT_LABELS[lift],
            "max_e1rm": best_e1rm["e1rm"],
            "max_weight": best_weight["weight_kg"],
            "best_set": best_e1rm,
        }
    return prs
