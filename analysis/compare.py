#!/usr/bin/env python3
"""2冊の目次を突き合わせて、一致・対立・片方だけを取り出す.

横断分析(aggregate.py)は「何冊が言っていたか」を数えるものだが、
こちらは2冊を正面から比べる回のために使う。

    python3 compare.py b05 b13        # プロンプトを2つ作る
    python3 compare.py --aggregate    # 答えを読んで compare_report.md を出す

採用基準は aggregate.py と同じ考え方で、2回の実行で一致したものだけを採る。
目次の項目名は原文をそのまま引用させるので、実行間で表記がぶれない。
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOKS_CSV = BASE / "books.csv"
BOOKS_DIR = BASE / "books"
OUT_DIR = BASE / "compare_out"
RESP_DIR = BASE / "responses_compare"
RUNS = 2

HEADER = """あなたは2冊の本の目次を突き合わせて、主張の異同を整理するアナリストです。

これから2冊の書籍情報を渡します。それぞれの目次を1項目ずつ読み、
**2冊の主張がどこで一致し、どこで対立し、どこが片方にしか無いか**を整理してください。

ルール:
- `a` と `b` には、**目次の項目名を原文のまま**書き写すこと(要約しない)
- `topic` は「その論点を一言で表したもの」を20文字以内で書く
- 対立(conflict)は、**同じ論点について反対のことを言っている**場合だけ
  似ているだけ、違う話をしているだけのものは対立ではない
- 一致(agree)は、同じ論点について同じ方向のことを言っている場合
- 確信が持てないものは含めない。推測で足さない
- only_a / only_b は、その本にしか無い論点の目次項目を原文のまま入れる(各最大12件)

出力は次のJSONだけ。前後に説明文をつけないでください。

```json
{{
  "book_a": "{a}",
  "book_b": "{b}",
  "conflict": [{{"topic": "論点", "a": "A側の目次項目", "b": "B側の目次項目"}}],
  "agree":    [{{"topic": "論点", "a": "A側の目次項目", "b": "B側の目次項目"}}],
  "only_a":   ["A側の目次項目"],
  "only_b":   ["B側の目次項目"]
}}
```

============ ここから書籍情報 ============
"""


def load_books():
    if not BOOKS_CSV.exists():
        sys.exit("books.csv がありません。")
    with BOOKS_CSV.open(encoding="utf-8-sig") as f:
        return {r["id"].strip(): r for r in csv.DictReader(f) if r.get("id")}


def norm(t):
    return re.sub(r"[\s　・･:：]+", "", (t or "").strip())


def make_prompts(aid, bid):
    books = load_books()
    for i in (aid, bid):
        if i not in books:
            sys.exit(f"{i} が books.csv にありません。")
        if not (BOOKS_DIR / f"{i}.md").exists():
            sys.exit(f"books/{i}.md がありません。")

    body = []
    for label, bid_ in (("A", aid), ("B", bid)):
        text = re.sub(r"<!--.*?-->", "", (BOOKS_DIR / f"{bid_}.md").read_text(encoding="utf-8"),
                      flags=re.S).strip()
        body.append(f"\n--- {label} / book_id: {bid_} / 書名: {books[bid_]['title']} ---\n{text}\n")

    OUT_DIR.mkdir(exist_ok=True)
    RESP_DIR.mkdir(exist_ok=True)
    prompt = HEADER.format(a=aid, b=bid) + "".join(body)
    for run in range(1, RUNS + 1):
        (OUT_DIR / f"pair_run{run}.txt").write_text(prompt, encoding="utf-8")

    print(f"A: {books[aid]['title']}")
    print(f"B: {books[bid]['title']}")
    print(f"プロンプトを{RUNS}個 作りました({len(prompt):,}文字): {OUT_DIR}\n")
    print("次にやること(2回とも「新しいチャット」で):")
    for run in range(1, RUNS + 1):
        print(f"  touch responses_compare/pair_run{run}.txt && "
              f"open -e compare_out/pair_run{run}.txt responses_compare/pair_run{run}.txt")
    print("\n  終わったら python3 compare.py --aggregate")


def read_runs():
    if not RESP_DIR.exists() or not any(RESP_DIR.glob("*.txt")):
        sys.exit(f"{RESP_DIR}/ に答えがありません。")
    runs = []
    for path in sorted(RESP_DIR.glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        data = None
        for cand in re.findall(r"```(?:json)?\s*(.*?)```", text, re.S) + [text]:
            try:
                data = json.loads(cand.strip())
                break
            except (json.JSONDecodeError, ValueError):
                continue
        if not isinstance(data, dict):
            print(f"  [警告] {path.name}: JSONを読み取れませんでした")
            continue
        runs.append(data)
    if not runs:
        sys.exit("読み取れた答えがありません。")
    return runs


def aggregate():
    runs = read_runs()
    need = min(2, len(runs))

    def pairs(key):
        seen = {}
        for r in runs:
            got = set()
            for item in r.get(key, []) or []:
                k = (norm(item.get("a")), norm(item.get("b")))
                if not any(k):
                    continue
                got.add(k)
                seen.setdefault(k, {"n": 0, "item": item})
            for k in got:
                seen[k]["n"] += 1
        return [v["item"] for v in seen.values() if v["n"] >= need]

    def singles(key):
        seen = {}
        for r in runs:
            for line in r.get(key, []) or []:
                k = norm(line)
                if k:
                    seen.setdefault(k, {"n": 0, "line": line})["n"] += 1
        return [v["line"] for v in seen.values() if v["n"] >= need]

    conflict, agree = pairs("conflict"), pairs("agree")
    only_a, only_b = singles("only_a"), singles("only_b")
    a = runs[0].get("book_a", "A")
    b = runs[0].get("book_b", "B")

    out = ["# 2冊の突き合わせレポート", "",
           "※compare.py が自動生成しています。",
           f"※{len(runs)}回の実行のうち{need}回以上で一致したものだけを採用", "",
           "## 数字", "",
           f"- 対立していた論点: **{len(conflict)}個**",
           f"- 一致していた論点: **{len(agree)}個**",
           f"- {a} にしか無い論点: **{len(only_a)}個**",
           f"- {b} にしか無い論点: **{len(only_b)}個**", "",
           "## 対立していた論点", "", "| 論点 | A | B |", "|---|---|---|"]
    for c in conflict:
        out.append(f"| {c.get('topic','')} | {c.get('a','')} | {c.get('b','')} |")
    out += ["", "## 一致していた論点", "", "| 論点 | A | B |", "|---|---|---|"]
    for c in agree:
        out.append(f"| {c.get('topic','')} | {c.get('a','')} | {c.get('b','')} |")
    out += ["", f"## {a} にしか無い論点", ""] + [f"- {l}" for l in only_a]
    out += ["", f"## {b} にしか無い論点", ""] + [f"- {l}" for l in only_b]

    (BASE / "compare_report.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"対立 {len(conflict)}個 / 一致 {len(agree)}個 / "
          f"{a}のみ {len(only_a)}個 / {b}のみ {len(only_b)}個")
    print("\n出力: compare_report.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="比べる2冊のid(例: b05 b13)")
    ap.add_argument("--aggregate", action="store_true", help="答えを読んでレポートを出す")
    args = ap.parse_args()

    if args.aggregate:
        aggregate()
    elif len(args.ids) == 2:
        make_prompts(*args.ids)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
