#!/usr/bin/env python3
"""books.csv の書式チェック.

STEP 2 の作業(1冊ずつのコピペ)に入る前に、リストが壊れていないか確かめる。

    python3 check_books.py
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOKS_CSV = BASE / "books.csv"
BOOKS_DIR = BASE / "books"
VALID_ORIGIN = {"和書", "洋書", ""}


def parse_sections(text):
    """Markdownを「## 見出し」単位に分解する."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    sections, cur = {}, "_head"
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)", line)
        if m:
            cur = m.group(1).strip()
            sections.setdefault(cur, [])
        else:
            sections.setdefault(cur, []).append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def report_content(rows):
    """各書籍の入力状況を一覧にする(これを見せてもらえば中身の確認ができる)."""
    tpl_path = BOOKS_DIR / "_template.md"
    tpl = parse_sections(tpl_path.read_text(encoding="utf-8")) if tpl_path.exists() else {}

    print("\n書籍データの状態:")
    done, empty, missing, thin = 0, [], [], []
    for r in rows:
        bid = (r.get("id") or "").strip()
        path = BOOKS_DIR / f"{bid}.md"
        if not path.exists():
            missing.append(bid)
            print(f"  {bid}  ファイルがありません")
            continue
        sec = parse_sections(path.read_text(encoding="utf-8"))
        toc = sec.get("目次", "")
        intro = sec.get("紹介文・帯のコピー", "")
        # 雛形の文言のままなら未記入とみなす
        if toc == tpl.get("目次", ""):
            toc = ""
        if intro == tpl.get("紹介文・帯のコピー", ""):
            intro = ""
        toc_lines = len([l for l in toc.splitlines() if l.strip()])
        chars = len(toc) + len(intro)
        flag = ""
        if chars < 20:
            empty.append(bid)
            flag = "  ← 中身が入っていません"
        elif toc_lines < 3:
            thin.append(bid)
            flag = "  ← 目次が薄い(紹介文だけでも進められます)"
        else:
            done += 1
        print(f"  {bid}  目次{toc_lines:3d}行  {chars:5d}字{flag}")

    print(f"\n合計 {len(rows)}冊 / 十分 {done}冊 / 目次少なめ {len(thin)}冊 "
          f"/ 未記入 {len(empty)}冊 / ファイルなし {len(missing)}冊")
    if empty or missing:
        print("未記入のものを埋めてから STEP 3 に進んでください:")
        for bid in (missing + empty)[:5]:
            print(f"  open -e books/{bid}.md")
        return False
    print("\nすべて揃っています。次に進めます:")
    print("  python3 make_prompts.py")
    return True


def init_book_files(rows):
    """books.csv に書かれたidぶんだけ、入力用ファイルを作る(既存は上書きしない)."""
    template = (BOOKS_DIR / "_template.md").read_text(encoding="utf-8")
    created = []
    for r in rows:
        bid = (r.get("id") or "").strip()
        path = BOOKS_DIR / f"{bid}.md"
        if bid and not path.exists():
            path.write_text(template, encoding="utf-8")
            created.append(path.name)
    if created:
        print(f"\n入力用ファイルを {len(created)}個 作りました: books/")
    else:
        print("\n入力用ファイルはすべて揃っています(既存のものは触っていません)。")
    print("1つずつ開いて、Amazonの内容紹介と目次を貼り付けてください:")
    print(f"  open -e books/{(rows[0].get('id') or 'b01').strip()}.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true",
                    help="books.csv のidぶん、books/ に入力用ファイルを作る")
    args = ap.parse_args()

    if not BOOKS_CSV.exists():
        sys.exit("books.csv がありません。books.sample.csv をコピーして作ってください。")

    with BOOKS_CSV.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]

    problems, notes = [], []

    need = ["id", "title", "author", "year", "origin"]
    missing_cols = [c for c in need if c not in cols]
    if missing_cols:
        problems.append(f"1行目の見出しが足りません: {', '.join(missing_cols)}\n"
                        f"    1行目は「{','.join(need)}」である必要があります。")

    if not rows:
        sys.exit("本が1冊も入っていません。")

    ids = [(r.get("id") or "").strip() for r in rows]
    dupes = [i for i, n in Counter(ids).items() if n > 1]
    if dupes:
        problems.append(f"idが重複しています: {', '.join(dupes)}")

    bad_id = [i for i in ids if not re.fullmatch(r"b\d{2}", i)]
    if bad_id:
        problems.append(f"idの形式が違います(b01のような小文字b+2桁): {', '.join(bad_id)}")

    expected = [f"b{i:02d}" for i in range(1, len(rows) + 1)]
    if sorted(ids) != sorted(expected):
        problems.append(f"idが b01〜b{len(rows):02d} の連番になっていません。")

    for r in rows:
        if not (r.get("title") or "").strip():
            problems.append(f"{r.get('id')}: 書名が空です")
        origin = (r.get("origin") or "").strip()
        if origin not in VALID_ORIGIN:
            problems.append(f"{r.get('id')}: originが「{origin}」です。"
                            "「和書」か「洋書」か空欄にしてください")
        if r.get(None):     # 列が多い = 書名のカンマが原因
            problems.append(f"{r.get('id')}: 列が多すぎます。"
                            "書名にカンマが入っていませんか?入るなら \"...\" で囲んでください")

    counts = Counter((r.get("origin") or "").strip() or "未設定" for r in rows)
    print(f"{len(rows)}冊 読み込みました。")
    print("  " + " / ".join(f"{k} {v}冊" for k, v in sorted(counts.items())))

    if len(rows) < 10:
        notes.append(f"{len(rows)}冊 です。少なすぎると共通点が出にくくなります"
                     "(10冊以上を推奨)。")
    if counts.get("未設定"):
        notes.append(f"originが未設定の本が {counts['未設定']}冊 あります"
                     "(空欄でも集計は通ります)。")

    for n in notes:
        print(f"  [メモ] {n}")

    if problems:
        print(f"\n直すところが {len(problems)}件 あります:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    if args.init:
        init_book_files(rows)
    elif any((BOOKS_DIR / f"{(r.get('id') or '').strip()}.md").exists() for r in rows):
        report_content(rows)
    else:
        print("\n書式は問題ありません。次は入力用ファイルを作ります:")
        print("  python3 check_books.py --init")


if __name__ == "__main__":
    main()
