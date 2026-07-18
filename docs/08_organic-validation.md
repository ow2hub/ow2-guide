# ステップ3(無料版): 組織的検証 — コミュニティ投稿で需要を見る

広告(Google=P-MAXの罠 / X=サブスク必須)を一旦回避し、**¥0で需要の第一感**を取る。
LP・デモ・フォーム・GA4は完成済みなので、リンクを貼るだけで計測できる。

## リンク(チャネルごとにUTMを変える=GA4で流入元が分かる)

- X(自分の垢): `https://ow2hub.github.io/shiftrhythm/lp/?utm_source=x&utm_medium=organic&utm_campaign=val01`
- 掲示板/コミュニティ: `https://ow2hub.github.io/shiftrhythm/lp/?utm_source=community&utm_medium=organic&utm_campaign=val01`
- note/ブログ: `https://ow2hub.github.io/shiftrhythm/lp/?utm_source=note&utm_medium=organic&utm_campaign=val01`

## 判定(無料版の合格ライン)
- LP到達(GA4のセッション)に対する **事前登録 CVR ≥ 5%** なら手応えあり → 有料(Google検索/Meta)へ
- 反応ゼロ〜極少 → 訴求か対象を変える。それでもダメなら候補①(配信者ツール)へ

---

## 投稿文(コピペ用)

宣伝くさくすると弾かれる/滑る。**「当事者が自作した、需要を知りたい」**の体で。

### ① X(自分のアカウント)— 共感ファースト
```
夜勤明け、結局いつ寝ればいいのか毎回わからん…って交代勤務あるある。

シフトを入れるだけで「寝る・光を浴びる・食べる」ベストな時間を提案するアプリ作ってます。2交代も3交代もOK。夜勤明けの過ごし方も出る。

同じ交代勤務の人に需要あるか知りたいです。デモ無料で触れます👇
https://ow2hub.github.io/shiftrhythm/lp/?utm_source=x&utm_medium=organic&utm_campaign=val01

#夜勤 #交代勤務 #工場勤務
```

### ② X(2本目・機能ファースト / 画像に週間バンドのスクショ推奨)
```
交代勤務者のための生活リズムアプリ「シフトリズム」試作。

・シフトはブロックでポンと入力（不規則でもOK）
・その日の睡眠/光/食事の整え方を提案
・"今は寝てる=起こさないで"を家族に共有

夜勤明け→翌日昼勤みたいなキツい並びは警告も出ます。
デモ→ https://ow2hub.github.io/shiftrhythm/lp/?utm_source=x&utm_medium=organic&utm_campaign=val01
```

### ③ 掲示板/コミュニティ（5ch 工場・夜勤・交代勤務スレ、LINEオープンチャット等）
```
工場の3交代やってる者ですが、夜勤明けの睡眠タイミングにいつも悩むので、
シフト入れると「寝る/光/食事」の時間を提案してくれるアプリを自作しました。

同じ交代勤務の人に需要あるか知りたくて。デモ無料で触れます。
https://ow2hub.github.io/shiftrhythm/lp/?utm_source=community&utm_medium=organic&utm_campaign=val01

こういうの欲しい人います？ 感想もらえると助かります。
```
※ スレの空気を読んで、宣伝連投はしない。1スレ1回、会話に混ぜる。

### ④ note/ブログ（体験談として書く→末尾にリンク）
```
タイトル案: 「3交代の睡眠地獄を、アプリで解決しようとしてる話」
本文: 夜勤明けの睡眠問題 → 既存アプリの不満(記録だけ) → 自作した提案アプリ
→ デモリンク → 「使ってみたい人は事前登録で早期割引」
リンク: https://ow2hub.github.io/shiftrhythm/lp/?utm_source=note&utm_medium=organic&utm_campaign=val01
```

## 投稿のコツ
- **1日1〜2チャネル**に絞る(一気に連投すると スパム判定/炎上リスク)
- 反応(いいね/コメント/クリック)を見て、刺さった訴求を次に厚くする
- コメントには誠実に返信 → それ自体が"当事者が作ってる"証明になり信頼になる

## 計測(数日後に見るもの)
- GA4: `utm_source` 別のセッション数、`cta_click` 数
- Googleフォーム: 事前登録の回答数 と 勤務形態の内訳(2交代/3交代)
- → CVR(登録÷セッション)を出して、有料に進むか判断
