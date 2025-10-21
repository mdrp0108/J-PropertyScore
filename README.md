# J‑PropertyScore API

**緯度経度から「地価×最寄駅×用途地域」を統合し、0–100の資産性スコアを返す** 無料基盤構成のミニAPI。  
Cloudflare Workers（無料枠）＋ 公的オープンデータ（MLIT Reinfolib）＋ GitHub Actions/Pages で **運用コストゼロ**・**高安定**を目指します。

![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![platform](https://img.shields.io/badge/platform-Cloudflare%20Workers-lightgrey)
![status](https://img.shields.io/badge/status-production--ready-brightgreen)

---

## 特長

- **1エンドポイント**：`/score?lat=...&lng=...` だけで、地価・駅・用途を統合した **資産性スコア** を返却
- **部分成功OK**：外部APIの一部が不調でも、取得できた要素だけで **ダイナミック重み** によるスコア算出
- **キャッシュ/フォールバック**：7日キャッシュ、**stale‑if‑error** 風の返却、**年次×ズーム** フォールバック
- **自己記述**：`/openapi.json` で **OpenAPI 仕様** を自己提供
- **観測性**：全応答に **`x-request-id`**、本文にも `request_id`／`sources.*.status`／`warnings` を同梱

---

## クイックスタート

### 1) 必要なもの
- Cloudflare アカウント（無料）
- MLIT Reinfolib の API キー（無料申請）
- Node.js (Wrangler 利用時)

### 2) セットアップ
```bash
# 1) 取得したプロジェクトを配置
git clone <YOUR_REPO_URL>
cd j-propertyscore

# 2) Wrangler ログイン
npx wrangler login

# 3) Secrets（APIキー）をCloudflareに登録
npx wrangler secret put REINFOLIB_API_KEY
# プロンプトが出たら MLIT の API キーを貼り付ける

# 4) デプロイ
npx wrangler deploy
