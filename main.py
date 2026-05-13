#!/usr/bin/env python3
"""
hevy-tracker — BIG3 weekly analysis runner.

Usage:
  python main.py              # run full analysis + email + Excel update
  python main.py --no-email   # skip email (useful for local testing)
  python main.py --dry-run    # print report only, no file writes
"""
import argparse
import os
import sys
from pathlib import Path

from src.hevy_client import HevyClient
from src.big3_analyzer import (
    aggregate_by_week,
    get_current_and_prev_week,
    analyze_week,
    compare_weeks,
    generate_menu_suggestions,
    all_time_prs,
)
from src.excel_reporter import write_report, OUTPUT_PATH
from src.email_notifier import send_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-email", action="store_true", help="Skip sending email")
    parser.add_argument("--dry-run",  action="store_true", help="Print only, no file writes")
    args = parser.parse_args()

    api_key = os.environ.get("HEVY_API_KEY", "")
    if not api_key:
        print("ERROR: HEVY_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print("⏳ Hevy APIからワークアウトデータを取得中...")
    client  = HevyClient(api_key)
    workouts = client.get_all_workouts()
    print(f"   {len(workouts)} workouts fetched.")

    records = client.get_big3_sets(workouts)
    print(f"   {len(records)} BIG3 sets found.")

    if not records:
        print("⚠ BIG3のセットデータが見つかりませんでした。")
        print("  ベンチプレス（バーベル）・デッドリフト（バーベル）・スクワット（バーベル）を")
        print("  Hevyに記録してください。")
        # still send a notification so the user knows the job ran
        if not args.no_email and not args.dry_run:
            _send_empty_notification()
        return

    weekly_data = aggregate_by_week(records)
    curr_key, prev_key = get_current_and_prev_week(records)

    print(f"\n📊 分析週: {curr_key}  （前週: {prev_key}）")

    curr_analysis = analyze_week(records, curr_key)
    comparison    = compare_weeks(records, curr_key, prev_key)
    prs           = all_time_prs(records)
    suggestions   = generate_menu_suggestions(comparison)

    # ── print summary ──────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print(f"BIG3 週次レポート {curr_key}")
    print("=" * 50)
    for lift, data in comparison.items():
        if data is None:
            print(f"  {lift}: データなし")
        else:
            print(
                f"  {data['label']:10s}  推定1RM {data['curr_e1rm']:.1f}kg  "
                f"（先週比 {data['e1rm_diff']:+.1f}kg）  {data['trend']}"
            )

    print("\n【来週のメニュー提案】")
    for s in suggestions:
        print(f"  {s}")

    # ── Excel ──────────────────────────────────────────────────────────────
    excel_path: Path | None = None
    if not args.dry_run:
        print("\n📝 Excelファイルを更新中...")
        excel_path = write_report(records, weekly_data, prs, OUTPUT_PATH)
        print(f"   保存: {excel_path}")

    # ── Email ──────────────────────────────────────────────────────────────
    if not args.no_email and not args.dry_run:
        print("\n📧 メール送信中...")
        try:
            send_report(curr_key, curr_analysis, comparison, prs, suggestions, excel_path)
        except KeyError as e:
            print(f"   ⚠ Email設定の環境変数が不足しています: {e}")
            print("   EMAIL_FROM / EMAIL_TO / EMAIL_PASSWORD を設定してください。")

    print("\n✅ 完了!")


def _send_empty_notification() -> None:
    """Send a minimal email when no BIG3 data exists yet."""
    import smtplib
    from email.mime.text import MIMEText

    email_from = os.environ.get("EMAIL_FROM", "")
    email_to   = os.environ.get("EMAIL_TO", "")
    email_pass = os.environ.get("EMAIL_PASSWORD", "")
    if not (email_from and email_to and email_pass):
        return

    msg = MIMEText(
        "今週はBIG3（ベンチプレス・デッドリフト・スクワット）のデータが記録されていません。\n"
        "来週はぜひトレーニングを記録してください！",
        "plain", "utf-8"
    )
    msg["Subject"] = "[BIG3] 今週のデータなし"
    msg["From"]    = email_from
    msg["To"]      = email_to

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(email_from, email_pass)
        server.sendmail(email_from, email_to, msg.as_bytes())


if __name__ == "__main__":
    main()
