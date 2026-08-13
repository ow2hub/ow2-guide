#!/usr/bin/env python3
"""AIに貼り付けるプロンプトを組み立てる.

books.csv と books/*.md を読んで、10冊ずつまとめたプロンプトを作る。
30冊なら 3バッチ × 3回 = 9個のファイルができるので、
それを1つずつAIに貼り付けて、返ってきた答えを responses/ に保存すればよい。

    python3 make_prompts.py

出力: prompts_out/batch1_run1.txt … batch3_run3.txt
"""

import argparse
import csv
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOKS_CSV = BASE / "books.csv"
BOOKS_DIR = BASE / "books"
OUT_DIR = BASE / "prompts_out"
BATCH_SIZE = 10
RUNS = 3

HEADER = """あなたは書籍のメタデータから、その本が読者に勧めている「行動レベルの主張」を
抽出するアナリストです。

これから{n}冊分の書籍情報を渡します。それぞれについて、
**その本が読者に勧めている行動**を抽出してください。

ルール:
- 1件につき20文字以内、動詞で終わる短文にする(例:「やらないことを決める」)
- 抽象的な理念(例:「人生を豊かにする」)は除外し、実行できる行動だけを残す
- 1冊あたり最大12件。書かれていないことを推測で足さない
- 確信が持てないものは含めない
- 複数の本で同じ内容なら、同じ言い回しを使う

出力は次のJSONだけ。前後に説明文をつけないでください。

```json
[
  {{"book_id": "b01", "claims": ["主張1", "主張2"]}},
  {{"book_id": "b02", "claims": ["主張1", "主張2"]}}
]
```

============ ここから書籍情報 ============
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                    help=f"1回のプロンプトに入れる冊数(既定 {BATCH_SIZE})。"
                         "「長すぎる」と怒られたら 5 にする")
    args = ap.parse_args()
    batch_size = max(1, args.batch_size)

    if not BOOKS_CSV.exists():
        sys.exit(f"{BOOKS_CSV} がありません。\n"
                 f"books.sample.csv をコピーして books.csv を作り、30冊を書いてください。")
    with BOOKS_CSV.open(encoding="utf-8") as f:
        books = [r for r in csv.DictReader(f) if r.get("id")]
    if not books:
        sys.exit("books.csv に本が1冊も書かれていません。")

    missing = [b["id"] for b in books if not (BOOKS_DIR / f"{b['id']}.md").exists()]
    if missing:
        sys.exit("次の本のデータファイルがありません:\n  "
                 + "\n  ".join(f"books/{m}.md" for m in missing)
                 + "\n\nbooks/_template.md をコピーして作ってください。")

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()
    (BASE / "responses").mkdir(exist_ok=True)

    batches = [books[i:i + batch_size] for i in range(0, len(books), batch_size)]
    for bi, batch in enumerate(batches, 1):
        body = []
        for b in batch:
            text = (BOOKS_DIR / f"{b['id']}.md").read_text(encoding="utf-8").strip()
            body.append(f"\n--- book_id: {b['id']} / 書名: {b['title']} ---\n{text}\n")
        prompt = HEADER.format(n=len(batch)) + "".join(body)
        for run in range(1, RUNS + 1):
            (OUT_DIR / f"batch{bi}_run{run}.txt").write_text(prompt, encoding="utf-8")

    total = len(batches) * RUNS
    longest = max(len((OUT_DIR / f"batch{i}_run1.txt").read_text(encoding="utf-8"))
                  for i in range(1, len(batches) + 1))
    print(f"{len(books)}冊 → {len(batches)}バッチ × {RUNS}回 = {total}個のプロンプトを作りました。")
    print(f"一番長いプロンプト: 約{longest:,}文字")
    if longest > 60000:
        print("  ※長すぎてAIに入らないかもしれません。その場合は:")
        print("      python3 make_prompts.py --batch-size 5")
    print(f"場所: {OUT_DIR}\n")
    print("次にやること:")
    print(f"  1. prompts_out/batch1_run1.txt を開いて、中身を全部コピー")
    print( "  2. ChatGPT か Claude の新しいチャットに貼り付けて送信")
    print( "  3. 返ってきた答えをコピーして responses/batch1_run1.txt に保存")
    print(f"  4. これを {total} 個ぶん繰り返す(必ず毎回「新しいチャット」で)")
    print( "  5. 終わったら python3 aggregate.py")
    print("\n※同じ内容を3回投げるのは、AIの答えのブレを測るためです。")
    print("  毎回新しいチャットで実行しないと意味がなくなります。")


if __name__ == "__main__":
    main()
