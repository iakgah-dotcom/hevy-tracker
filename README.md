# 🏋️ hevy-tracker

Hevy API を使って **BIG3（ベンチプレス・デッドリフト・スクワット）** を毎週自動分析するシステム。

| 機能 | 内容 |
|---|---|
| 自動実行 | GitHub Actions で毎週月曜 AM 7:00 JST |
| データ取得 | Hevy API から全ワークアウトを取得 |
| 分析 | 推定1RM（Epley式）・総Volume・週次比較 |
| Excel | `data/BIG3_tracker.xlsx` を毎週更新・コミット |
| メール | HTMLレポート＋Excel添付をGmailで送信 |

## セットアップ

### 1. ローカルで試す

```bash
pip install -r requirements.txt

cp .env.example .env
# .env を編集して各値を設定

# 環境変数を読み込んで実行
set -a && source .env && set +a
python main.py --no-email   # メールなし
python main.py              # メールあり
python main.py --dry-run    # ファイル書き込みなし
```

### 2. GitHub Actions シークレットを設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を登録：

| シークレット名 | 値 |
|---|---|
| `HEVY_API_KEY` | Hevy の API キー |
| `EMAIL_FROM` | 送信元 Gmail アドレス |
| `EMAIL_TO` | 送信先メールアドレス |
| `EMAIL_PASSWORD` | Gmail アプリパスワード |

> **Gmail アプリパスワードの取得手順**  
> Google アカウント → セキュリティ → 2段階認証を有効化 →  
> 「アプリパスワード」を検索 → アプリを選択して生成

### 3. 手動実行

Actions タブ → "BIG3 Weekly Analysis" → "Run workflow" から即時実行できます。

## ファイル構成

```
hevy-tracker/
├── .github/workflows/
│   └── weekly_analysis.yml   # 毎週月曜 7:00 JST に自動実行
├── src/
│   ├── hevy_client.py        # Hevy API クライアント
│   ├── big3_analyzer.py      # BIG3 分析ロジック
│   ├── excel_reporter.py     # Excel レポート生成
│   └── email_notifier.py     # Gmail 送信
├── data/
│   └── BIG3_tracker.xlsx     # 自動更新される Excel
├── main.py                   # エントリーポイント
├── requirements.txt
└── .env.example
```

## 分析内容

- **推定1RM**：Epley式 `weight × (1 + reps/30)` で算出
- **週次比較**：先週比の増減（kg・%）とトレンド判定
- **ALL TIME PR**：全期間の最高推定1RMと最大重量
- **メニュー提案**：パフォーマンスに基づいた来週の練習提案

## BIG3 対応種目

| カテゴリ | 主種目 | バリアント |
|---|---|---|
| ベンチプレス | Bench Press (Barbell) | DB・SM・ワイドグリップ等 |
| デッドリフト | Deadlift (Barbell) | トラップバー・スモウ等 |
| スクワット | Squat (Barbell) | SM・ボックス・フロント等 |
