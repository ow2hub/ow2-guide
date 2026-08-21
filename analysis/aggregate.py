#!/usr/bin/env python3
"""30冊横断分析の集計スクリプト.

AIは主張の「抽出」だけを担当し、何冊に登場したかの「カウント」はここで
決定論的に行う。AIに数えさせると誤るため、集計は必ずこのスクリプトを通すこと。

入力:
    books.csv                     書誌リスト(id,title,author,year,origin)
    extracted/<id>_run<N>.json    抽出結果 {"book_id": "b01", "claims": [...]}
    canonical.json                名寄せ表 {"元の表現": "代表名"}(任意)

出力:
    report.md            全ランキング・和洋比較・1冊限定の主張一覧
    video_numbers.py     build_video.py の SCENES に貼れる数値ブロック

使い方:
    python3 aggregate.py                # 集計してレポート出力
    python3 aggregate.py --list-claims  # 名寄せプロンプトに渡す主張一覧を出力
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

MIN_AGREEMENT = 2      # 3回の実行のうち何回以上一致したら採用するか

# 対象ディレクトリ(--dir で変更可能)。既定はこのスクリプトのある場所。
BASE = Path(__file__).resolve().parent
BOOKS_CSV = EXTRACTED = RESPONSES = CANONICAL = None


def set_base(path):
    """入出力先のディレクトリを決める."""
    global BASE, BOOKS_CSV, EXTRACTED, RESPONSES, CANONICAL
    BASE = Path(path).resolve()
    BOOKS_CSV = BASE / "books.csv"
    EXTRACTED = BASE / "extracted"
    RESPONSES = BASE / "responses"
    CANONICAL = BASE / "canonical.json"


def load_books():
    if not BOOKS_CSV.exists():
        sys.exit(f"{BOOKS_CSV} がありません。books.sample.csv をコピーして作ってください。")
    with BOOKS_CSV.open(encoding="utf-8") as f:
        books = [r for r in csv.DictReader(f) if r.get("id")]
    if not books:
        sys.exit("books.csv に行がありません。")
    return books


def normalize(text):
    """表記ゆれの軽い吸収(全角空白・記号・句点の除去)."""
    t = text.strip().replace("　", "")
    t = re.sub(r"[。、,.\s]+$", "", t)
    return t


def extract_json_objects(text):
    """AIの返答から {"book_id":..., "claims":[...]} を取り出す(多少の崩れは許容)."""
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for cand in fenced + [text]:
        try:
            data = json.loads(cand.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        if isinstance(data, dict):
            return [data]
    # 最後の手段: book_id を含む { } を1つずつ拾う
    found = []
    for m in re.finditer(r'\{[^{}]*"book_id"[^{}]*\}', text, re.S):
        try:
            found.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            pass
    return found


def collect_runs():
    """book_id -> {実行回: 主張の集合} を集める.

    responses/batch*_run*.txt  (make_prompts.py を使う通常の流れ)
    extracted/<id>_run<N>.json (1冊ずつ手で作る旧形式)
    のどちらでも読める。
    """
    runs = defaultdict(lambda: defaultdict(set))
    files = []
    if RESPONSES.exists():
        files += sorted(RESPONSES.glob("*.txt")) + sorted(RESPONSES.glob("*.json"))
    if EXTRACTED.exists():
        files += sorted(EXTRACTED.glob("*.json"))
    if not files:
        sys.exit(f"{RESPONSES}/ にも {EXTRACTED}/ にも答えがありません。\n"
                 "make_prompts.py で作ったプロンプトをAIに投げ、\n"
                 "その返答を responses/batch1_run1.txt のように保存してください。")
    for path in files:
        m = re.search(r"run(\d+)", path.stem)
        run = int(m.group(1)) if m else 1
        text = path.read_text(encoding="utf-8")
        objs = extract_json_objects(text)
        if not objs:
            print(f"  [警告] {path.name} からJSONを読み取れませんでした。飛ばします。")
            continue
        for obj in objs:
            bid = obj.get("book_id")
            if not bid:
                continue
            claims = {normalize(c) for c in obj.get("claims", []) if normalize(c)}
            runs[bid][run] |= claims
    return runs


def load_canonical():
    """名寄せ表を読む。無ければ空の表を返す."""
    if not CANONICAL.exists():
        print("  [注意] canonical.json がないため、名寄せなしで集計します。")
        return {}
    table = json.loads(CANONICAL.read_text(encoding="utf-8"))
    return {normalize(k): normalize(v) for k, v in table.items()}


def load_extractions(books):
    """本ごとに、MIN_AGREEMENT 回以上出現した主張だけを採用して返す.

    名寄せは「一致を数える前」に適用する。実行ごとに言い回しが変わっても
    同じ主張として数えられるようにするため(後から名寄せすると、表現ゆれの
    せいで一致回数が足りず、正しい主張まで捨ててしまう)。
    """
    runs = collect_runs()
    table = load_canonical()
    adopted, stats = {}, {}
    for book in books:
        bid = book["id"]
        per_run = runs.get(bid)
        if not per_run:
            print(f"  [警告] {bid}({book['title']})の抽出結果が見つかりません。スキップします。")
            continue
        counter, raw = Counter(), set()
        for claims in per_run.values():
            raw |= claims
            counter.update({table.get(c, c) for c in claims})
        n_runs = len(per_run)
        need = min(MIN_AGREEMENT, n_runs)
        kept = sorted(c for c, n in counter.items() if n >= need)
        adopted[bid] = kept
        stats[bid] = {"runs": n_runs, "raw": len(raw), "kept": len(kept)}
    if not adopted:
        sys.exit("採用できた抽出結果が1件もありません。")
    return adopted, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-claims", action="store_true",
                    help="名寄せプロンプトに貼る主張一覧を出力して終了")
    ap.add_argument("--dir", default=None,
                    help="books.csv と extracted/ があるディレクトリ(既定: このスクリプトの場所)")
    args = ap.parse_args()

    set_base(args.dir or Path(__file__).resolve().parent)
    books = load_books()
    by_id = {b["id"]: b for b in books}

    if args.list_claims:
        # 名寄せ表を作るため、採用前の生の主張をすべて出す
        every = sorted({c for per_run in collect_runs().values()
                        for claims in per_run.values() for c in claims})
        print("\n".join(f"- {c}" for c in every))
        print(f"\n({len(every)}件)", file=sys.stderr)
        return

    adopted, stats = load_extractions(books)
    raw_total = sum(len(v) for v in adopted.values())
    merged = adopted

    # 主張 -> 登場した本のid
    appears = defaultdict(set)
    for bid, claims in merged.items():
        for c in claims:
            appears[c].add(bid)

    n_books = len(merged)
    ranking = sorted(appears.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    only_one = [c for c, ids in ranking if len(ids) == 1]

    # 和書/洋書の傾向
    origin_books = defaultdict(set)
    for bid in merged:
        origin_books[(by_id[bid].get("origin") or "").strip() or "不明"].add(bid)

    # ---- report.md -------------------------------------------------------
    out = ["# 30冊横断分析レポート", "",
           "※このレポートは aggregate.py が自動生成しています。",
           f"※採用基準: 同一書籍で{MIN_AGREEMENT}回以上の実行で一致した主張のみ", "",
           "## 全体の数字", "",
           f"- 分析した本: **{n_books}冊**",
           f"- 抽出された主張(名寄せ前・延べ): **{raw_total}個**",
           f"- ユニークな主張(名寄せ後): **{len(appears)}個**",
           f"- 1冊にしか登場しなかった主張: **{len(only_one)}個**", ""]

    for label, threshold in (("20冊以上", 20), ("15冊以上", 15)):
        hits = [(c, ids) for c, ids in ranking if len(ids) >= threshold]
        out += [f"- {label}に登場した主張: **{len(hits)}個**"]
    out += ["", "## 主張ランキング", "", "| 順位 | 主張 | 登場冊数 |", "|---:|---|---:|"]
    for i, (c, ids) in enumerate(ranking, 1):
        out.append(f"| {i} | {c} | {len(ids)}/{n_books} |")

    out += ["", "## 1冊にしか出てこなかった主張(動画の「差分」パート用)", ""]
    for c in only_one:
        bid = next(iter(appears[c]))
        out.append(f"- 「{c}」 — {by_id[bid]['title']}")

    out += ["", "## 和書 / 洋書 の傾向", ""]
    for origin, ids in sorted(origin_books.items()):
        out.append(f"### {origin}({len(ids)}冊)")
        local = Counter()
        for c, cids in appears.items():
            hit = len(cids & ids)
            if hit:
                local[c] = hit
        for c, n in local.most_common(8):
            out.append(f"- {c}: {n}/{len(ids)}冊")
        out.append("")

    out += ["## 実行ごとのブレ(信頼性の記録)", "",
            "| 書籍 | 実行回数 | 延べ主張 | 採用 |", "|---|---:|---:|---:|"]
    for bid, s in stats.items():
        out.append(f"| {by_id[bid]['title']} | {s['runs']} | {s['raw']} | {s['kept']} |")

    (BASE / "report.md").write_text("\n".join(out) + "\n", encoding="utf-8")

    # ---- video_numbers.py ------------------------------------------------
    top = ranking[:3]
    next4 = ranking[3:7]
    lines = ["# build_video.py の SCENES に貼るための数値(自動生成)", "",
             f"N_BOOKS = {n_books}",
             f"TOTAL_RAW_CLAIMS = {raw_total}",
             f"UNIQUE_CLAIMS = {len(appears)}",
             f"ONLY_ONE_BOOK = {len(only_one)}", "",
             "# POINT 1 の横棒グラフ", "TOP3_BARS = ["]
    for c, ids in top:
        lines.append(f'    ("{c}", {len(ids)}, {n_books}),')
    lines += ["]", "", "# 4位〜7位の横棒グラフ", "NEXT4_BARS = ["]
    for c, ids in next4:
        lines.append(f'    ("{c}", {len(ids)}, {n_books}),')
    lines += ["]", "",
              "# 「意外な少数派」パート: 調べたいキーワードをここに書いて数字を確認する",
              "WATCHLIST = {"]
    for kw in ("早起き", "朝活", "ポモドーロ", "マルチタスク"):
        hit = [(c, len(ids)) for c, ids in ranking if kw in c]
        lines.append(f'    "{kw}": {hit},')
    lines += ["}", "",
              "# 1冊にしかない主張(動画の POINT 3 で紹介する候補)", "ONLY_ONE_LIST = ["]
    for c in only_one[:20]:
        lines.append(f'    "{c}",')
    lines.append("]")
    (BASE / "video_numbers.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"分析した本: {n_books}冊")
    print(f"延べ主張: {raw_total} → ユニーク: {len(appears)} → 1冊限定: {len(only_one)}")
    print("トップ3:")
    for c, ids in top:
        print(f"  {c}: {len(ids)}/{n_books}")
    print("\n出力: report.md / video_numbers.py")


if __name__ == "__main__":
    main()
