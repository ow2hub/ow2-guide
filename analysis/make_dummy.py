#!/usr/bin/env python3
"""仮動画用のダミーデータを生成する(パイプラインの動作確認も兼ねる).

動画で使う数字が「集計結果として実際にありうる形」になっているかを、
本物と同じ aggregate.py に通して検証するためのフィクスチャ生成器。

    python3 make_dummy.py          # dummy/ 以下に一式生成
    cd dummy && python3 ../aggregate.py

出力される数字が build_video.py の SCENES と一致していれば、
台本の数値は少なくとも内部矛盾のない集計結果になっている。

※これはあくまでダミー。公開用の動画には実際に集計した値を使うこと。
"""

import csv
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "dummy"
N_BOOKS = 30
N_YOSHO = 14          # 洋書(翻訳書)の冊数。残りが和書

# (主張, 登場冊数) — この分布がそのまま動画のグラフの数字になる
TIER_A = [("やらないことを決める", 24), ("重要と緊急を分ける", 22),
          ("似た作業はまとめて処理する", 21)]
TIER_B = [("マルチタスクをやめる", 18), ("時間を記録する", 17),
          ("先延ばしの原因を潰す", 16), ("休憩を先に予定に入れる", 15)]
TIER_C = [("タスクを分解する", 13), ("締め切りを自分で決める", 12),
          ("完璧を目指さない", 11), ("会議を減らす", 10),
          ("ポモドーロを使う", 9), ("早起きする", 8),
          ("通知を切る", 7), ("朝活をする", 6),
          ("移動時間を活用する", 5), ("場所を変えて集中する", 4),
          ("睡眠を優先する", 4), ("ToDoを1日3つに絞る", 3),
          ("週次でふりかえる", 3), ("断る練習をする", 2),
          ("頼まれごとを即答しない", 2)]
# 1冊にしか出てこない主張(動画の POINT 3 で使う「差分」)
TIER_D = ["予定表に「やらないこと」を書く", "疲れているときに決断しない",
          "「時間がない」を「優先順位が低い」に言い換える",
          "朝一番にメールを開かない", "会議は立ったまま行う",
          "1日の終わりに明日の3件を決める", "使わない持ち物を減らす",
          "移動を伴う予定を同じ曜日に寄せる", "作業BGMを固定する",
          "紙のノートに手で書く", "月曜の午前を空けておく",
          "返信の期限を自分で宣言する", "定例会議を四半期で見直す",
          "検索より人に聞く", "集中できた時間帯を記録する",
          "タスクに所要時間を書いてから始める", "誘いは即答せず一晩置く",
          "終業時刻を先に決める", "やめた習慣のリストを持つ"]


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "responses").mkdir(parents=True)

    # 書誌リスト
    rows = [["id", "title", "author", "year", "origin"]]
    for i in range(1, N_BOOKS + 1):
        rows.append([f"b{i:02d}", f"ダミー時間術本{i:02d}", f"著者{i:02d}",
                     2015 + i % 10, "洋書" if i <= N_YOSHO else "和書"])
    with (OUT / "books.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)

    # 主張を書籍に割り当てる(登場冊数がちょうど指定どおりになるように分散)
    per_book = {f"b{i:02d}": [] for i in range(1, N_BOOKS + 1)}
    offset = 0
    for claim, count in TIER_A + TIER_B + TIER_C:
        for j in range(count):
            bid = f"b{(offset + j) % N_BOOKS + 1:02d}"
            per_book[bid].append(claim)
        offset = (offset + 7) % N_BOOKS      # 偏らないようにずらす
    for k, claim in enumerate(TIER_D):
        per_book[f"b{k % N_BOOKS + 1:02d}"].append(claim)

    # 本番と同じ形式(10冊ずつのバッチ × 3回)で AI の返答を模擬する
    #   本命の主張 → 3回すべてに入れる(2回以上一致なので採用される)
    #   ノイズ     → 1回だけ入れる(採用されない = フィルタが効くことの確認)
    ids = sorted(per_book)
    batches = [ids[i:i + 10] for i in range(0, len(ids), 10)]
    for bi, batch in enumerate(batches, 1):
        for run in (1, 2, 3):
            payload = []
            for bid in batch:
                out = list(per_book[bid])
                if run == 2:
                    out.append(f"{bid}のノイズ主張")
                payload.append({"book_id": bid, "claims": out})
            body = "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"
            (OUT / "responses" / f"batch{bi}_run{run}.txt").write_text(body, encoding="utf-8")

    total = sum(len(v) for v in per_book.values())
    unique = len(TIER_A) + len(TIER_B) + len(TIER_C) + len(TIER_D)
    print(f"生成しました: {OUT}")
    print(f"  書籍: {N_BOOKS}冊(洋書{N_YOSHO} / 和書{N_BOOKS - N_YOSHO})")
    print(f"  延べ主張: {total}個 / ユニーク: {unique}種類 / 1冊限定: {len(TIER_D)}個")
    print(f"  1冊あたり平均: {total / N_BOOKS:.1f}個")
    print(f"\n確認するには:  cd {OUT.name} && python3 ../aggregate.py")


if __name__ == "__main__":
    main()
