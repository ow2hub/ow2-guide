# ステップ3 準備チェックリスト(オーナー作業・上から順に)

目的: LPを公開し、広告→事前登録の数字を計測できる状態にする。所要 合計1〜2時間+広告審査待ち。

---

## A. 事前登録フォームを作る(Google Forms・無料)

1. https://forms.google.com で新規フォーム作成。タイトル「シフトリズム 事前登録」
2. 質問を2つだけ作る(多いと登録率が落ちる):
   - **Q1 メールアドレス**(記述式・必須。設定→回答→「メールアドレスを収集する」でも可)
   - **Q2 勤務形態**(ラジオボタン・必須): `2交代(日勤/夜勤)` / `3交代(早番/遅番/夜勤)` / `その他・変則`
3. 「送信」→ リンクアイコン → 短縮URL(`https://forms.gle/xxxx`)をコピー
4. `lp/index.html` の `const FORM_URL = "..."` をそのURLに差し替え

## B. アクセス計測を入れる(GA4・無料)

1. https://analytics.google.com でプロパティ作成 → データストリーム(ウェブ)を追加
2. 「測定ID」`G-XXXXXXXXXX` をコピー
3. `lp/index.html` の先頭にある `<!-- ▼ GA4 ... ▼ -->` のコメントを外し(`<!--` と `-->` を削除)、
   2箇所の `G-XXXXXXXXXX` を自分の測定IDに差し替え
4. これで `page_view` と、CTAボタンの `cta_click`(設置済み)が計測される

## C. LPを公開する(GitHub Pages・無料)

- このリポジトリ(ow2hub/ow2-guide)の Settings → Pages
- Source: Deploy from a branch → Branch: `claude/solo-app-dev-cycle-36qhdj` / フォルダ: `/ (root)`
- 数分後、`https://ow2hub.github.io/ow2-guide/lp/` で公開される
- ※ A・Bの差し替えをコミット&プッシュしてから公開すること(または公開後に反映)

## D. 広告を入稿する(予算 合計¥10,000)

### D-1. Google検索広告(¥5,000・intentが強く判定しやすい主軸)
- キーワード(完全一致〜フレーズ一致):
  `夜勤明け 寝れない` / `三交代 生活リズム` / `夜勤 睡眠 コツ` / `交代勤務 体調管理` / `二交代 きつい 対策`
- 見出し案: 「交代勤務の生活リズム、アプリが提案」「夜勤明け、いつ寝る?を解決」
- 遷移先: 公開したLPのURL + `?utm_source=google&utm_medium=cpc&utm_campaign=pretest01`
- 1日の上限を¥700程度に設定し、7日で使い切る

### D-2. X(Twitter)広告(¥5,000・共感訴求)
- ターゲティング: キーワード `夜勤`/`交代勤務`/`三交代`、興味関心=仕事/健康
- クリエイティブ3案(docs/03_ad-test.md 参照)。画像は週間バンドのスクショが有効
- 遷移先: LPのURL + `?utm_source=twitter&utm_medium=cpc&utm_campaign=pretest01`

## E. 7〜10日後にやること

- GA4で セッション数 / `cta_click` 数、Formsで 登録数 を集計
- このセッション(または新セッション)に「クリック数・CVR・登録数・各媒体のCPC」を共有
  → CPA計算と GO / PIVOT / STOP 判定(docs/03_ad-test.md の基準)を一緒にやる

---

### 差し替えが必要な箇所まとめ(`lp/index.html`)
| 場所 | 現在の値 | 差し替える値 |
|---|---|---|
| `FORM_URL`(script内) | `https://forms.gle/XXXXXXXXXXXX` | 自分のフォームURL |
| GA4 コメント2箇所 | `G-XXXXXXXXXX` | 自分の測定ID(+コメント解除) |
