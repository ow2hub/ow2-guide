#!/usr/bin/env python3
"""目次をまとめて1ファイルに貼り、books/*.md に流し込む.

15冊ぶんのファイルを1つずつ開くのは手間なので、目次だけは1枚の紙にまとめて
貼れるようにする。エディタを開くのは1回で済む。

    python3 paste_tocs.py --init    # tocs.md を作る(見出しだけ入っている)
    open -e tocs.md                 # 各見出しの下に目次を貼る
    python3 paste_tocs.py           # books/*.md の「## 目次」に流し込む

貼り忘れた本は飛ばすだけなので、何日かに分けて少しずつ進めてもよい。
既に目次が入っている本は、--force を付けない限り上書きしない。
"""

import argparse
import csv
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
BOOKS_CSV = BASE / "books.csv"
BOOKS_DIR = BASE / "books"
TOCS = BASE / "tocs.md"
SECTION = "目次"
MARK = re.compile(r"^===\s*(b\d{2})\b.*$")

GUIDE = """# 目次の貼り付けシート

# 「=== bNN / 書名 ===」の行は消さないでください。その下に目次を貼るだけです。
# 途中まででも構いません。貼っていない本は飛ばされます。
#
# 目次のありか(上から順に試すのが早い):
#   1. Kindleの「サンプルを読む」… 目次は冒頭にあるのでサンプルで足ります
#   2. Amazon商品ページの「なか見!検索」
#   3. honto / 楽天ブックス / 版元ドットコム / 出版社サイト
#
# 本文はコピーしないこと。使ってよいのは目次だけです。
"""


def load_books():
    if not BOOKS_CSV.exists():
        sys.exit("books.csv がありません。先に STEP 1 をやってください。")
    with BOOKS_CSV.open(encoding="utf-8-sig") as f:
        books = [r for r in csv.DictReader(f) if (r.get("id") or "").strip()]
    if not books:
        sys.exit("books.csv に本が1冊も書かれていません。")
    return books


def split_sections(text):
    """Markdownを [(見出し, 本文)] に分解する(見出しの順序は保つ)."""
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out, cur, buf = [], "_head", []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+)", line)
        if m:
            out.append((cur, "\n".join(buf)))
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    out.append((cur, "\n".join(buf)))
    return out


def current_toc(path, template_toc):
    for name, body in split_sections(path.read_text(encoding="utf-8")):
        if name == SECTION:
            body = body.strip()
            return "" if body == template_toc else body
    return ""


def write_toc(path, toc):
    """books/bNN.md の「## 目次」だけを差し替える(他の節はそのまま)."""
    raw = path.read_text(encoding="utf-8")
    trailer = "".join(re.findall(r"<!--.*?-->", raw, flags=re.S))
    parts, found = [], False
    for name, body in split_sections(raw):
        if name == SECTION:
            body, found = "\n" + toc.strip() + "\n", True
        parts.append((name, body))
    if not found:
        parts.append((SECTION, "\n" + toc.strip() + "\n"))
    out = []
    for name, body in parts:
        if name != "_head":
            out.append(f"\n## {name}")
        out.append(body.strip("\n"))
    text = "\n".join(out).strip("\n") + "\n"
    if trailer:
        text += "\n" + trailer.strip() + "\n"
    path.write_text(text, encoding="utf-8")


def do_init(books, template_toc):
    have = []
    blocks = [GUIDE]
    for b in books:
        bid = b["id"].strip()
        path = BOOKS_DIR / f"{bid}.md"
        if path.exists() and current_toc(path, template_toc):
            have.append(bid)
            continue
        blocks.append(f"\n=== {bid} / {b.get('title', '').strip()} ===\n\n")
    if TOCS.exists():
        sys.exit(f"{TOCS.name} がすでにあります。中身を流し込むなら:\n"
                 "  python3 paste_tocs.py\n"
                 f"作り直すなら先に消してください: rm {TOCS.name}")
    TOCS.write_text("".join(blocks), encoding="utf-8")
    todo = len(blocks) - 1
    print(f"{TOCS.name} を作りました({todo}冊ぶんの見出し)。")
    if have:
        print(f"  目次が入っている {len(have)}冊 は入れていません: {', '.join(have)}")
    print("\n次にやること:")
    print("  1. open -e tocs.md")
    print("  2. 各見出しの下に目次を貼る(途中まででOK)")
    print("  3. python3 paste_tocs.py")


def do_apply(books, template_toc, force):
    if not TOCS.exists():
        sys.exit(f"{TOCS.name} がありません。先に:\n  python3 paste_tocs.py --init")
    known = {b["id"].strip() for b in books}
    blocks, cur = {}, None
    for line in TOCS.read_text(encoding="utf-8").splitlines():
        m = MARK.match(line)
        if m:
            cur = m.group(1)
            blocks[cur] = []
        elif cur:
            blocks[cur].append(line)

    unknown = sorted(set(blocks) - known)
    if unknown:
        print(f"  [警告] books.csv に無いidが書かれています: {', '.join(unknown)}")

    wrote, empty, kept, missing = [], [], [], []
    for bid, lines in blocks.items():
        if bid not in known:
            continue
        toc = "\n".join(lines).strip()
        path = BOOKS_DIR / f"{bid}.md"
        if not path.exists():
            missing.append(bid)
            continue
        if not toc:
            empty.append(bid)
            continue
        if current_toc(path, template_toc) and not force:
            kept.append(bid)
            continue
        write_toc(path, toc)
        wrote.append((bid, len([l for l in toc.splitlines() if l.strip()])))

    for bid, n in wrote:
        print(f"  {bid}  目次{n:3d}行 を書き込みました")
    if kept:
        print(f"\n  既に目次があるので触っていません({', '.join(kept)})。"
              "\n  上書きしたいときは --force を付けてください。")
    if missing:
        print(f"\n  [警告] books/ にファイルがありません: {', '.join(missing)}"
              "\n  python3 check_books.py --init で作れます。")
    if empty:
        print(f"\n  まだ貼っていない本: {', '.join(empty)}")
        print("  tocs.md はそのまま残してあるので、続きを貼ってまた実行してください。")

    print(f"\n{len(wrote)}冊 に書き込みました。")
    if not empty and not missing:
        print("全部そろいました。次に進めます:")
        print("  python3 check_books.py")
        print("  python3 make_prompts.py        # 目次も使う(--intro-only は付けない)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="tocs.md(貼り付けシート)を作る")
    ap.add_argument("--force", action="store_true", help="既に目次がある本も上書きする")
    args = ap.parse_args()

    books = load_books()
    tpl = BOOKS_DIR / "_template.md"
    template_toc = ""
    if tpl.exists():
        for name, body in split_sections(tpl.read_text(encoding="utf-8")):
            if name == SECTION:
                template_toc = body.strip()

    if args.init:
        do_init(books, template_toc)
    else:
        do_apply(books, template_toc, args.force)


if __name__ == "__main__":
    main()
