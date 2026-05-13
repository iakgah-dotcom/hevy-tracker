"""Send weekly BIG3 report via Gmail SMTP."""
import os
import smtplib
from datetime import date
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any


LIFT_EMOJI = {"bench": "🏋️", "deadlift": "💀", "squat": "🦵"}
TREND_EMOJI = {"↑ 上昇": "📈", "→ 維持": "➡️", "↓ 下降": "📉"}


def _fmt(val: float | None, unit: str = "kg", decimals: int = 1) -> str:
    if val is None or val == 0:
        return "—"
    return f"{val:.{decimals}f}{unit}"


def _pct(val: float | None) -> str:
    if val is None:
        return ""
    sign = "+" if val >= 0 else ""
    return f"（{sign}{val:.1f}%）"


def build_html(
    curr_week: str,
    curr_analysis: dict[str, Any],
    comparison: dict[str, Any],
    prs: dict[str, Any],
    suggestions: list[str],
) -> str:
    today = date.today().isoformat()

    lift_rows = ""
    for lift in ["bench", "deadlift", "squat"]:
        cmp = comparison.get(lift)
        label = {"bench": "ベンチプレス", "deadlift": "デッドリフト", "squat": "スクワット"}[lift]
        emoji = LIFT_EMOJI[lift]

        if cmp is None:
            lift_rows += f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #eee;">
                {emoji} <strong>{label}</strong>
              </td>
              <td colspan="4" style="padding:10px;border-bottom:1px solid #eee;color:#999;">
                今週のデータなし
              </td>
            </tr>"""
            continue

        trend = cmp["trend"]
        trend_emoji = TREND_EMOJI.get(trend, "")
        e1rm_diff_str = f"{cmp['e1rm_diff']:+.1f}kg {_pct(cmp['e1rm_pct'])}" if cmp["curr_e1rm"] else "—"
        vol_diff_str  = f"{cmp['vol_diff']:+.0f}kg {_pct(cmp['vol_pct'])}" if cmp["curr_volume"] else "—"

        lift_rows += f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #eee;font-weight:bold;">
                {emoji} {label}
              </td>
              <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">
                {_fmt(cmp['curr_e1rm'])}
              </td>
              <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;color:{'#27ae60' if cmp['e1rm_diff']>0 else '#c0392b' if cmp['e1rm_diff']<0 else '#7f8c8d'};">
                {e1rm_diff_str}
              </td>
              <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">
                {_fmt(cmp['curr_volume'], unit='kg', decimals=0)}
              </td>
              <td style="padding:10px;border-bottom:1px solid #eee;text-align:center;">
                {trend_emoji} {trend}
              </td>
            </tr>"""

    # PR rows
    pr_rows = ""
    for lift in ["bench", "deadlift", "squat"]:
        pr = prs.get(lift, {})
        label = {"bench": "ベンチプレス", "deadlift": "デッドリフト", "squat": "スクワット"}[lift]
        emoji = LIFT_EMOJI[lift]
        best = pr.get("best_set")
        pr_rows += f"""
            <tr>
              <td style="padding:8px;">{emoji} {label}</td>
              <td style="padding:8px;text-align:center;">{_fmt(pr.get('max_e1rm'))}</td>
              <td style="padding:8px;text-align:center;">{_fmt(pr.get('max_weight'))}</td>
              <td style="padding:8px;text-align:center;">{best['date'].isoformat() if best else '—'}</td>
            </tr>"""

    suggestion_html = "".join(
        f"<li style='margin:6px 0;'>{s}</li>" if s.strip() else "<li style='list-style:none;height:6px;'></li>"
        for s in suggestions
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>BIG3 週次レポート</title></head>
<body style="font-family:'Meiryo',sans-serif;background:#f4f6f9;margin:0;padding:20px;">
  <div style="max-width:700px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1);">

    <!-- header -->
    <div style="background:linear-gradient(135deg,#1F4E79,#2E75B6);padding:30px;color:#fff;">
      <h1 style="margin:0;font-size:22px;">🏋️ BIG3 週次トレーニングレポート</h1>
      <p style="margin:8px 0 0;opacity:.85;">{curr_week}  ／  作成日: {today}</p>
    </div>

    <!-- this week summary -->
    <div style="padding:24px;">
      <h2 style="color:#1F4E79;border-left:4px solid #2E75B6;padding-left:10px;">今週の成績</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#EBF3FB;">
            <th style="padding:10px;text-align:left;">種目</th>
            <th style="padding:10px;">推定1RM</th>
            <th style="padding:10px;">先週比</th>
            <th style="padding:10px;">総Volume</th>
            <th style="padding:10px;">トレンド</th>
          </tr>
        </thead>
        <tbody>{lift_rows}</tbody>
      </table>
    </div>

    <!-- all-time PRs -->
    <div style="padding:0 24px 24px;">
      <h2 style="color:#1F4E79;border-left:4px solid #C00000;padding-left:10px;">歴代ベスト (ALL TIME PR)</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#FDE9E9;">
            <th style="padding:8px;text-align:left;">種目</th>
            <th style="padding:8px;">推定1RM</th>
            <th style="padding:8px;">最大重量</th>
            <th style="padding:8px;">達成日</th>
          </tr>
        </thead>
        <tbody>{pr_rows}</tbody>
      </table>
    </div>

    <!-- suggestions -->
    <div style="padding:0 24px 24px;">
      <h2 style="color:#1F4E79;border-left:4px solid #70AD47;padding-left:10px;">来週のメニュー提案</h2>
      <ul style="line-height:1.8;color:#333;">{suggestion_html}</ul>
    </div>

    <!-- footer -->
    <div style="background:#1F4E79;color:#fff;padding:16px;text-align:center;font-size:12px;">
      hevy-tracker — Powered by Hevy API × GitHub Actions
    </div>
  </div>
</body>
</html>"""


def build_plain(
    curr_week: str,
    comparison: dict[str, Any],
    prs: dict[str, Any],
    suggestions: list[str],
) -> str:
    lines = [f"BIG3 週次レポート ({curr_week})", "=" * 40, ""]

    lines.append("【今週の成績】")
    for lift in ["bench", "deadlift", "squat"]:
        cmp = comparison.get(lift)
        label = {"bench": "ベンチプレス", "deadlift": "デッドリフト", "squat": "スクワット"}[lift]
        if cmp is None:
            lines.append(f"  {label}: データなし")
        else:
            lines.append(
                f"  {label}: 推定1RM {_fmt(cmp['curr_e1rm'])}  "
                f"（先週比 {cmp['e1rm_diff']:+.1f}kg）  {cmp['trend']}"
            )

    lines += ["", "【歴代ベスト】"]
    for lift in ["bench", "deadlift", "squat"]:
        pr = prs.get(lift, {})
        label = {"bench": "ベンチプレス", "deadlift": "デッドリフト", "squat": "スクワット"}[lift]
        lines.append(f"  {label}: 推定1RM {_fmt(pr.get('max_e1rm'))}  最大重量 {_fmt(pr.get('max_weight'))}")

    lines += ["", "【来週のメニュー提案】"]
    lines.extend(suggestions)

    return "\n".join(lines)


def send_report(
    curr_week: str,
    curr_analysis: dict[str, Any],
    comparison: dict[str, Any],
    prs: dict[str, Any],
    suggestions: list[str],
    excel_path: Path | None = None,
) -> None:
    smtp_host   = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port   = int(os.environ.get("SMTP_PORT", "587"))
    email_from  = os.environ["EMAIL_FROM"]
    email_to    = os.environ["EMAIL_TO"]
    email_pass  = os.environ["EMAIL_PASSWORD"]

    subject = f"[BIG3] 週次レポート {curr_week}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = email_from
    msg["To"]      = email_to

    plain = build_plain(curr_week, comparison, prs, suggestions)
    html  = build_html(curr_week, curr_analysis, comparison, prs, suggestions)

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    # attach Excel if present
    if excel_path and excel_path.exists():
        with open(excel_path, "rb") as f:
            part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=excel_path.name)
        msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(email_from, email_pass)
        server.sendmail(email_from, email_to, msg.as_bytes())

    print(f"Email sent to {email_to}")
