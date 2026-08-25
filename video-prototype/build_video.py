#!/usr/bin/env python3
"""仮動画ビルダー v2 — 漫画風ポップアニメ + キャラ掛け合い + VOICEVOX対応.

「AI実践読書ラボ」第1回:
  『時間術の本15冊の「Amazon紹介文」を分析したら、共通点がゼロだった』

  数値は実データ(analysis/ で集計した結果)。集計手順は analysis/START_HERE.md、
  復元用の抽出結果と名寄せ表は analysis/recovered/ にある。

特徴:
  - 2キャラの掛け合い台本(吹き出し=字幕を兼ねる漫画レイアウト)
  - 口パク(音声の音量に同期) / まばたき / 体の上下ゆれ / 吹き出しポップイン
  - 横棒グラフ・大数字のカウントアップ・集中線などのポップ演出
  - 音声は VOICEVOX(推奨) → 無ければ Open JTalk にフォールバック
  - フレームは ffmpeg に直接パイプするので中間PNGを吐かない

音声エンジン:
  VOICEVOX を使う場合は先にエンジンを起動しておく(Macならアプリを起動するだけ)。
      既定の接続先: http://127.0.0.1:50021
  起動していれば自動検出して VOICEVOX を使う。検出できなければ Open JTalk。

  ※VOICEVOXは無料・商用利用可だが、キャラクターごとに利用規約があり
    クレジット表記(例: VOICEVOX:ずんだもん)が必要。概要欄に必ず記載すること。
  ※本スクリプトが描画するキャラ絵はオリジナルの簡易イラストであり、
    VOICEVOXキャラクターの立ち絵ではない(立ち絵は別途ライセンスが必要)。

使い方:
    python3 build_video.py <出力ディレクトリ> [--engine voicevox|openjtalk|auto]
"""

import argparse
import json
import math
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# 基本設定
# ---------------------------------------------------------------------------
W, H = 1280, 720
FPS = 15
CHANNEL = "AI実践読書ラボ"
WATERMARK = ""          # 仮ビルド中の注記。公開版は空にしておく



def _pick_font(candidates):
    """環境にある日本語フォントを順に探す(macOS / Linux 両対応)."""
    for path in candidates:
        if Path(path).exists():
            return path
    raise SystemExit(
        "日本語フォントが見つかりません。build_video.py の FONT_BOLD / FONT_REG に\n"
        "手元のフォントのパスを指定してください。候補として探した場所:\n  "
        + "\n  ".join(candidates))


FONT_BOLD = _pick_font([
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",          # Linux
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",                 # macOS
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/NotoSansCJKjp-Bold.otf",
])
FONT_REG = _pick_font([
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/NotoSansCJKjp-Regular.otf",
])
VOICEVOX_URL = "http://127.0.0.1:50021"
OJT_DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
OJT_VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"

# ポップな配色
CREAM = (255, 249, 235)
INK = (38, 42, 66)
PINK = (255, 108, 145)
YELLOW = (255, 201, 71)
MINT = (86, 208, 184)
SKY = (108, 178, 255)
PURPLE = (154, 124, 235)
WHITE = (255, 255, 255)

# 話者定義: VOICEVOXのspeaker IDと、Open JTalkフォールバック時の声色パラメータ
# VOICEVOX speaker id 例: 2=四国めたん(ノーマル) 3=ずんだもん(ノーマル)
#                        8=春日部つむぎ 11=玄野武宏 13=青山龍星 14=冥鳴ひまり
SPEAKERS = {
    "noa": {    # 後輩・生徒・ツッコミ役
        "name": "ノア",
        "voicevox": 8,          # 春日部つむぎ
        "ojt": {"fm": 5.0, "rate": 1.05},
        "body": (128, 214, 238), "hair": (86, 196, 172), "side": "left",
        "style": "twin",        # ツインテール + 前髪ぱっつん
    },
    "mei": {    # 先輩・解説役
        "name": "メイ先生",
        "voicevox": 2,          # 四国めたん
        "ojt": {"fm": -1.0, "rate": 1.0},
        "body": PINK, "hair": (206, 78, 118), "side": "right",
        "style": "long",        # ロングヘア + メガネ
    },
}

LINE_PAUSE = 0.34
SCENE_PAUSE = 0.8

# ---------------------------------------------------------------------------
# 台本
#   visual: bullets / stat / bars   impact=True で集中線
#   lines : sp(話者) text(吹き出し表示) tts(読み上げ用/省略時はtext)
# ---------------------------------------------------------------------------
SCENES = [
    # ---- OP フック ---------------------------------------------------------
    {
        "chapter": "15冊の紹介文を分析した結果",
        "chip": "OP",
        "visual": {"type": "stat", "kicker": "今回の検証", "num": "15", "unit": "冊",
                   "label": "時間術の本のAmazon紹介文だけを分析"},
        "lines": [
            {"sp": "noa", "text": "先生!時間術の本15冊の、Amazonの紹介文だけを集めてみました",
             "tts": "先生!時間術の本じゅうごさつの、アマゾンの紹介文だけを集めてみました"},
            {"sp": "mei", "text": "あら、本文じゃなくて紹介文だけ?"},
            {"sp": "noa", "text": "はい。売り文句だけでどこまで分かるのか知りたくて"},
            {"sp": "mei", "text": "面白い実験ね。結果はかなり残酷だったけれど"},
        ],
    },
    {
        "chip": "OP",
        "impact": True,
        "visual": {"type": "stat", "kicker": "15冊すべてに共通していた主張は",
                   "num": "0", "unit": "個", "label": "一番多いものでも、15冊中3冊だけ"},
        "lines": [
            {"sp": "mei", "text": "15冊すべてに共通していた主張は、ゼロだったの",
             "tts": "じゅうごさつすべてに共通していた主張は、ゼロだったの"},
            {"sp": "noa", "text": "ゼロ!? ひとつも無いんですか?"},
            {"sp": "mei", "text": "ええ。一番多いものでも、15冊中3冊だけ",
             "tts": "ええ。一番多いものでも、じゅうごさつちゅう、さんさつだけ"},
            {"sp": "noa", "text": "同じ「時間術」の本なのに…?"},
            {"sp": "mei", "text": "そう。ここから面白い話になるわ"},
        ],
    },
    # ---- 予告 --------------------------------------------------------------
    {
        "chapter": "この動画でわかること",
        "chip": "予告",
        "visual": {"type": "bullets", "kicker": "この動画でわかること",
                   "title": "紹介文の分析でわかった3つ",
                   "items": ["① 15冊の紹介文に共通点が無かったという事実",
                             "② なぜそんなことが起きるのか",
                             "③ じゃあ何を見て本を選べばいいのか"]},
        "lines": [
            {"sp": "mei", "text": "今日わかることは3つよ", "tts": "今日わかることはみっつよ"},
            {"sp": "mei", "text": "1つ目、15冊の紹介文に共通点が無かったという事実",
             "tts": "ひとつめ、じゅうごさつの紹介文に共通点が無かったという事実"},
            {"sp": "mei", "text": "2つ目、なぜそんなことが起きるのか",
             "tts": "ふたつめ、なぜそんなことが起きるのか"},
            {"sp": "mei", "text": "3つ目、じゃあ何を見て本を選べばいいのか",
             "tts": "みっつめ、じゃあ何を見て本を選べばいいのか"},
            {"sp": "noa", "text": "3つ目、めちゃくちゃ実用的ですね"},
            {"sp": "mei", "text": "今日の話は、全部そこにつながるわ"},
        ],
    },
    # ---- 検証方法 ----------------------------------------------------------
    {
        "chapter": "どうやって集めたか",
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "どうやって選んだか",
                   "title": "選書に主観を入れない",
                   "items": ["Kindleストアの時間術カテゴリの売れ筋ランキングから",
                             "上から機械的に選ぶ",
                             "ジャンル違いと著者の重複だけ外して15冊"]},
        "lines": [
            {"sp": "mei", "text": "まず、どうやって集めたかを正直に話すわ"},
            {"sp": "mei", "text": "Kindleストアの時間術カテゴリの売れ筋ランキングから選んだの"},
            {"sp": "mei", "text": "上から順に、機械的にね"},
            {"sp": "noa", "text": "好きな本を選ばなかったんですね"},
            {"sp": "mei", "text": "選り好みすると、結論が最初から歪んでしまうもの"},
            {"sp": "mei", "text": "ジャンル違いと著者の重複だけ外して、15冊になったわ",
             "tts": "ジャンル違いと著者の重複だけ外して、じゅうごさつになったわ"},
        ],
    },
    {
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "何をAIに渡したか",
                   "title": "使ったのは紹介文だけ",
                   "items": ["Amazonの商品説明(いわゆる売り文句)",
                             "本文は使っていない",
                             "全部を同じ条件に揃えるのが大事"]},
        "lines": [
            {"sp": "mei", "text": "次に、AIに渡したデータ",
             "tts": "次に、エーアイに渡したデータ"},
            {"sp": "mei", "text": "使ったのはAmazonの商品説明、いわゆる紹介文だけよ",
             "tts": "使ったのはアマゾンの商品説明、いわゆる紹介文だけよ"},
            {"sp": "noa", "text": "本文は使っていないんですか?"},
            {"sp": "mei", "text": "使っていないわ。著作権的にグレーだし、今回は売り文句を調べたかったの"},
            {"sp": "noa", "text": "なるほど、あえて紹介文だけなんですね"},
            {"sp": "mei", "text": "そう。全部を同じ条件に揃えるのが大事なのよ"},
        ],
    },
    {
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "先に答えておきます",
                   "title": "「AIの分析、信用できるの?」",
                   "items": ["同じ処理を2回まわした",
                             "両方に出た主張だけを採用",
                             "1回しか出なかったものは全部捨てた"]},
        "lines": [
            {"sp": "noa", "text": "でも先生、AIの分析って信用できるんですか?",
             "tts": "でも先生、エーアイの分析って信用できるんですか?"},
            {"sp": "mei", "text": "いい質問。正直に言うと、そのままだと信用できないわ"},
            {"sp": "noa", "text": "えっ"},
            {"sp": "mei", "text": "同じデータを渡しても、実行するたびに言い回しが変わるの"},
            {"sp": "mei", "text": "だから2回まわして、両方に出た主張だけを採用したわ",
             "tts": "だからにかいまわして、両方に出た主張だけを採用したわ"},
            {"sp": "noa", "text": "1回しか出なかったものは?", "tts": "いっかいしか出なかったものは?"},
            {"sp": "mei", "text": "全部捨てたわ。ブレたものは数えないの"},
        ],
    },
    {
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "分析パイプライン",
                   "title": "延べ21個 → 13種類",
                   "items": ["2回とも出た主張: 延べ21個",
                             "同じ意味をまとめると: 13種類",
                             "15冊すべてに登場したもの: 0個"]},
        "lines": [
            {"sp": "mei", "text": "そうやって残ったのが、延べ21個の主張",
             "tts": "そうやって残ったのが、のべ、にじゅういっこの主張"},
            {"sp": "noa", "text": "15冊で21個…少なくないですか?",
             "tts": "じゅうごさつで、にじゅういっこ。少なくないですか?"},
            {"sp": "mei", "text": "1冊あたり1.4個ね。紹介文が短いから、こんなものよ",
             "tts": "いっさつあたり、いってんよんこね。紹介文が短いから、こんなものよ"},
            {"sp": "mei", "text": "同じ意味のものをまとめたら、13種類まで減ったわ",
             "tts": "同じ意味のものをまとめたら、じゅうさんしゅるいまで減ったわ"},
            {"sp": "noa", "text": "その13個の中に、共通点があるはずですよね?",
             "tts": "そのじゅうさんこの中に、共通点があるはずですよね?"},
        ],
    },
    {
        "chip": "検証方法",
        "visual": {"type": "stat", "kicker": "紹介文1本から取れた主張の数",
                   "num": "1.4", "unit": "個", "label": "200字読んでも、分かるのは1〜2個だけ"},
        "lines": [
            {"sp": "mei", "text": "この「1冊あたり1.4個」という数字、実はけっこう重要なの",
             "tts": "この、いっさつあたりいってんよんこという数字、実はけっこう重要なの"},
            {"sp": "noa", "text": "どういうことですか?"},
            {"sp": "mei", "text": "紹介文を全部読んでも、その本が何を勧めているかは1〜2個しか分からない",
             "tts": "紹介文を全部読んでも、その本が何を勧めているかは、いちこからにこしか分からない"},
            {"sp": "noa", "text": "200字読んで、1〜2個…", "tts": "にひゃくじ読んで、いちこからにこ"},
            {"sp": "mei", "text": "しかもその1〜2個が、これから見せる抽象的な言葉なのよ"},
        ],
    },
    # ---- POINT 1 -----------------------------------------------------------
    {
        "chapter": "共通点ランキング",
        "chip": "POINT 1/3",
        "visual": {"type": "bars", "kicker": "POINT 1 — 共通点ランキング",
                   "title": "15冊中、何冊が言っていたか",
                   "items": [("時間の使い方を見直す", 3, 15),
                             ("まとまった時間を確保する", 2, 15),
                             ("やることを減らす", 2, 15)]},
        "lines": [
            {"sp": "mei", "text": "これがランキングの上位よ"},
            {"sp": "mei", "text": "第1位、時間の使い方を見直す。15冊中3冊",
             "tts": "だいいちい、時間の使い方を見直す。じゅうごさつちゅう、さんさつ"},
            {"sp": "mei", "text": "2位と3位は、どちらも2冊",
             "tts": "にいとさんいは、どちらもにさつ"},
            {"sp": "noa", "text": "1位が3冊…想像より全然少ないです",
             "tts": "いちいがさんさつ。想像より全然少ないです"},
            {"sp": "mei", "text": "そうなの。15冊中3冊は、共通点とは呼べないわ",
             "tts": "そうなの。じゅうごさつちゅうさんさつは、共通点とは呼べないわ"},
        ],
    },
    {
        "chip": "POINT 1/3",
        "visual": {"type": "bullets", "kicker": "1位の中身を見てみる",
                   "title": "「時間の使い方を見直す」の正体",
                   "items": ["元の表現:「効率的に時間を使う」",
                             "「日常の無駄を削る」「限られた時間を活かす」",
                             "→ 言い換えただけで、中身がない"]},
        "lines": [
            {"sp": "mei", "text": "しかも、この1位の中身を見てほしいの",
             "tts": "しかも、このいちいの中身を見てほしいの"},
            {"sp": "mei", "text": "元の表現は「効率的に時間を使う」「日常の無駄を削る」"},
            {"sp": "mei", "text": "そして「限られた時間を活かす」よ"},
            {"sp": "noa", "text": "…全部おなじこと言ってません?"},
            {"sp": "mei", "text": "そう。だからひとつにまとめたの"},
            {"sp": "mei", "text": "でも問題は、これが具体的に何をしろと言っているのか分からないこと"},
            {"sp": "noa", "text": "確かに、明日から何をすればいいのか分かりません"},
        ],
    },
    {
        "chip": "POINT 1/3",
        "visual": {"type": "bars", "kicker": "2位以下も横並び",
                   "title": "どれも2冊ずつ",
                   "items": [("やることを減らす", 2, 15),
                             ("タスクを見える化する", 2, 15),
                             ("意識的に休む", 2, 15),
                             ("意志力に頼らない", 2, 15)]},
        "lines": [
            {"sp": "mei", "text": "2位以下も見てみましょう", "tts": "にい以下も見てみましょう"},
            {"sp": "mei", "text": "やることを減らす、タスクを見える化する"},
            {"sp": "mei", "text": "意識的に休む、意志力に頼らない"},
            {"sp": "mei", "text": "全部2冊ずつ。きれいに横並びよ", "tts": "全部にさつずつ。きれいに横並びよ"},
            {"sp": "noa", "text": "突出したものが、ひとつも無いんですね"},
            {"sp": "mei", "text": "つまり13種類の主張が、バラバラに散らばっているの",
             "tts": "つまりじゅうさんしゅるいの主張が、バラバラに散らばっているの"},
        ],
    },
    # ---- POINT 2(核心) ----------------------------------------------------
    {
        "chapter": "なぜ共通点が無いのか",
        "chip": "POINT 2/3",
        "impact": True,
        "visual": {"type": "bullets", "kicker": "POINT 2 — なぜ共通点が無いのか",
                   "title": "本がバラバラだから、ではない",
                   "items": ["中身が違うから共通点が無い、のではない",
                             "紹介文に中身が書かれていないから",
                             "15冊が同じ制約を受けているだけ"]},
        "lines": [
            {"sp": "noa", "text": "でも、なんで共通点が無いんでしょう"},
            {"sp": "mei", "text": "ここが今日の核心よ"},
            {"sp": "mei", "text": "本の中身がバラバラだから、ではないの"},
            {"sp": "noa", "text": "え、違うんですか?"},
            {"sp": "mei", "text": "紹介文に、中身が書かれていないからよ"},
            {"sp": "noa", "text": "えっ"},
        ],
    },
    {
        "chip": "POINT 2/3",
        "visual": {"type": "bullets", "kicker": "紹介文の役割",
                   "title": "紹介文は「説明」ではなく「宣伝」",
                   "items": ["目的は、買ってもらうこと",
                             "具体策を書くと「読んだ気」になられる",
                             "だから抽象的な言葉しか書けない"]},
        "lines": [
            {"sp": "mei", "text": "紹介文の目的は、説明することじゃなくて買ってもらうことなの"},
            {"sp": "mei", "text": "具体的なノウハウを全部書いてしまったら、どうなると思う?"},
            {"sp": "noa", "text": "…読んだ気になって、買わないですね"},
            {"sp": "mei", "text": "そういうこと。だから抽象的な言葉になるの"},
            {"sp": "mei", "text": "15冊が示し合わせたわけじゃない。全部が同じ制約を受けているだけ",
             "tts": "じゅうごさつが示し合わせたわけじゃない。全部が同じ制約を受けているだけ"},
            {"sp": "noa", "text": "売り文句としては、正しい行動なんですね…"},
        ],
    },
    {
        "chip": "POINT 2/3",
        "visual": {"type": "bullets", "kicker": "誤解しないでほしいこと",
                   "title": "悪いのは出版社ではない",
                   "items": ["紹介文は宣伝なのだから、それでいい",
                             "問題は、それを「説明」だと思って読んでいたこと",
                             "道具の使い方を間違えていただけ"]},
        "lines": [
            {"sp": "noa", "text": "これって、出版社が悪いって話ですか?"},
            {"sp": "mei", "text": "いいえ、全然。紹介文は宣伝なんだから、それでいいのよ"},
            {"sp": "mei", "text": "問題は、私たちがそれを「説明」だと思って読んでいたこと"},
            {"sp": "noa", "text": "期待する場所が、間違ってたと"},
            {"sp": "mei", "text": "そういうこと。道具の使い方を間違えていただけね"},
        ],
    },
    # ---- POINT 3(決定打) --------------------------------------------------
    {
        "chapter": "目次を足したら12個出てきた",
        "chip": "POINT 3/3",
        "impact": True,
        "visual": {"type": "stat", "kicker": "同じ本を「目次つき」で分析し直したら",
                   "num": "12", "unit": "個",
                   "label": "紹介文だけのときは、1個だった"},
        "lines": [
            {"sp": "mei", "text": "証拠を見せるわ。1冊だけ、目次も一緒に分析してみたの",
             "tts": "証拠を見せるわ。いっさつだけ、目次も一緒に分析してみたの"},
            {"sp": "mei", "text": "「タスク管理をなんとかしたいと思ったら最初に読む本」という本ね"},
            {"sp": "mei", "text": "紹介文だけのときに取れた主張は、1個",
             "tts": "紹介文だけのときに取れた主張は、いっこ"},
            {"sp": "noa", "text": "1個ですか", "tts": "いっこですか"},
            {"sp": "mei", "text": "でも目次を足したら、12個出てきたわ",
             "tts": "でも目次を足したら、じゅうにこ出てきたわ"},
            {"sp": "noa", "text": "12個!? 同じ本ですよね?", "tts": "じゅうにこ!? 同じ本ですよね?"},
        ],
    },
    {
        "chip": "POINT 3/3",
        "visual": {"type": "bullets", "kicker": "目次から出てきた具体策",
                   "title": "これが本の中身",
                   "items": ["タイムログをとる / 「なんでもリスト」をつくる",
                             "2分だけ戦法 / 週に1度クッションタイムを設ける",
                             "「いつでもいいですよ」を言わない"]},
        "lines": [
            {"sp": "mei", "text": "出てきたのは、こういう主張よ"},
            {"sp": "mei", "text": "タイムログをとる、なんでもリストをつくる、2分だけ戦法",
             "tts": "タイムログをとる、なんでもリストをつくる、にふんだけ戦法"},
            {"sp": "mei", "text": "「いつでもいいですよ」を言わない、というのもあったわ"},
            {"sp": "noa", "text": "めちゃくちゃ具体的ですね!"},
            {"sp": "mei", "text": "そう。これが本の中身なの"},
            {"sp": "mei", "text": "そしてこの12個のうち、紹介文に書かれていたものは1つも無かった",
             "tts": "そしてこのじゅうにこのうち、紹介文に書かれていたものは、ひとつも無かった"},
        ],
    },
    {
        "chip": "POINT 3/3",
        "visual": {"type": "bars", "kicker": "同じ本での比較",
                   "title": "紹介文からは1個、目次からは12個",
                   "items": [("紹介文から取れた主張", 1, 12),
                             ("目次から取れた主張", 12, 12)]},
        "lines": [
            {"sp": "mei", "text": "数字で見ると、こうよ"},
            {"sp": "noa", "text": "12倍…", "tts": "じゅうにばい"},
            {"sp": "mei", "text": "しかも重なりはゼロ。紹介文から取れた1個は、具体策ですらなかったわ",
             "tts": "しかも重なりはゼロ。紹介文から取れたいっこは、具体策ですらなかったわ"},
            {"sp": "noa", "text": "「自分に合うやり方を選ぶ」でしたね"},
            {"sp": "mei", "text": "そう。それは本の主張というより、当たり前の話ね"},
        ],
    },
    # ---- 結論 --------------------------------------------------------------
    {
        "chapter": "結論:紹介文で本を選ぶな",
        "chip": "結論",
        "impact": True,
        "visual": {"type": "bullets", "kicker": "今回の結論",
                   "title": "紹介文で本を選ぶな",
                   "items": ["紹介文 = どの本もほぼ同じ",
                             "目次 = 本ごとに全然違う",
                             "差が出るのは、目次から先"]},
        "lines": [
            {"sp": "mei", "text": "だから今日の結論はこうなるわ"},
            {"sp": "mei", "text": "紹介文は、どの本もほぼ同じことしか書いていない"},
            {"sp": "mei", "text": "差が出るのは、目次から先よ"},
            {"sp": "noa", "text": "紹介文を読んで「よさそう」と思ってたの、無意味だったんですね"},
            {"sp": "mei", "text": "無意味とは言わないけれど、選ぶ材料にはならないわね"},
            {"sp": "noa", "text": "けっこうショックです…"},
        ],
    },
    {
        "chapter": "今日からできること",
        "chip": "今日からできること",
        "visual": {"type": "bullets", "kicker": "買う前に目次を見る方法",
                   "title": "3分で確認できます",
                   "items": ["Kindleなら「サンプルを読む」で冒頭に目次がある",
                             "商品説明に目次を載せている本も多い",
                             "楽天ブックス・hontoの同じ本のページにも載っている"]},
        "lines": [
            {"sp": "noa", "text": "じゃあ、目次ってどこで見られるんですか?"},
            {"sp": "mei", "text": "Kindle本なら「サンプルを読む」。冒頭に目次が入っているわ"},
            {"sp": "mei", "text": "商品説明の中に、目次をそのまま載せている本も多いの"},
            {"sp": "mei", "text": "楽天ブックスやhontoの同じ本のページにも、載っていることがあるわ"},
            {"sp": "noa", "text": "3分あれば確認できますね", "tts": "さんぷんあれば確認できますね"},
            {"sp": "mei", "text": "その3分で、失敗する買い物がかなり減るはずよ",
             "tts": "そのさんぷんで、失敗する買い物がかなり減るはずよ"},
        ],
    },
    # ---- 限界の開示 --------------------------------------------------------
    {
        "chapter": "この分析の限界",
        "chip": "正直な話",
        "visual": {"type": "bullets", "kicker": "この分析の限界",
                   "title": "数字は「目安」として見てほしい",
                   "items": ["15冊は少ない。増やせば結果は変わりうる",
                             "今回のランキングは個人出版の本が中心だった",
                             "紹介文の長さにも本ごとの差がある"]},
        "lines": [
            {"sp": "mei", "text": "最後に、この分析の限界も言っておくわ"},
            {"sp": "mei", "text": "まず15冊は少ないわ。増やせば違う結果が出るかもしれない",
             "tts": "まずじゅうごさつは少ないわ。増やせば違う結果が出るかもしれない"},
            {"sp": "mei", "text": "今回のランキングは、個人出版の本が中心だったの"},
            {"sp": "noa", "text": "大きい出版社の本だと、違うかもしれない?"},
            {"sp": "mei", "text": "その可能性はあるわ。紹介文の長さにも差があったしね"},
            {"sp": "noa", "text": "そこまで言われると、逆に信用できます"},
            {"sp": "mei", "text": "断言する人より、限界を言う人を信じたほうがいいわよ"},
        ],
    },
    # ---- まとめ + 次回 -----------------------------------------------------
    {
        "chapter": "まとめ",
        "chip": "まとめ",
        "visual": {"type": "bullets", "kicker": "今日のまとめ",
                   "title": "15冊分析の結論",
                   "items": ["15冊の紹介文に、共通点はゼロだった",
                             "紹介文は宣伝であって、説明ではない",
                             "本を選ぶなら、目次を見る"]},
        "lines": [
            {"sp": "mei", "text": "まとめるわ。15冊の紹介文に、共通点はゼロ",
             "tts": "まとめるわ。じゅうごさつの紹介文に、共通点はゼロ"},
            {"sp": "mei", "text": "一番多いものでも、3冊だけだったわ", "tts": "一番多いものでも、さんさつだけだったわ"},
            {"sp": "mei", "text": "それは紹介文が宣伝であって、説明ではないから"},
            {"sp": "mei", "text": "本を選ぶなら、目次を見ること"},
            {"sp": "noa", "text": "今日から何をすればいいですか?"},
            {"sp": "mei", "text": "次に本を買うとき、紹介文を読む前に目次を開いてみて"},
            {"sp": "noa", "text": "みなさんは紹介文だけで本を買ったこと、ありますか?"},
            {"sp": "noa", "text": "よかったらコメントで教えてください!"},
        ],
    },
    {
        "chapter": "次回予告",
        "chip": "次回予告",
        "visual": {"type": "bullets", "kicker": "次回予告",
                   "title": "次は15冊ぜんぶの目次で同じ分析",
                   "items": ["今日と正反対の結果が出るかもしれない",
                             "毎週金曜 19時 更新",
                             "チャンネル登録で次回の検証をお見逃しなく"]},
        "lines": [
            {"sp": "mei", "text": "次回は、15冊ぜんぶの目次を集めて、同じ分析をやるわ",
             "tts": "次回は、じゅうごさつぜんぶの目次を集めて、同じ分析をやるわ"},
            {"sp": "noa", "text": "今日と正反対の結果が出るかもしれないんですね"},
            {"sp": "mei", "text": "そうなったら面白いでしょう"},
            {"sp": "mei", "text": "気に入ったらチャンネル登録をお願いね"},
            {"sp": "noa", "text": "それでは、また次の動画で!"},
        ],
    },
]


# ---------------------------------------------------------------------------
# 音声合成
# ---------------------------------------------------------------------------
def voicevox_available(base=VOICEVOX_URL):
    try:
        with urllib.request.urlopen(f"{base}/version", timeout=3) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def tts_voicevox(text, speaker_id, out_wav, base=VOICEVOX_URL):
    q = urllib.parse.urlencode({"text": text, "speaker": speaker_id})
    req = urllib.request.Request(f"{base}/audio_query?{q}", method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        query = json.load(r)
    query["speedScale"] = 1.05
    query["prePhonemeLength"] = 0.05
    query["postPhonemeLength"] = 0.1
    body = json.dumps(query).encode()
    req = urllib.request.Request(
        f"{base}/synthesis?speaker={speaker_id}", data=body, method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out_wav.write_bytes(r.read())


def tts_openjtalk(text, cfg, out_wav):
    txt = out_wav.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    subprocess.run(
        ["open_jtalk", "-x", OJT_DIC, "-m", OJT_VOICE,
         "-fm", str(cfg["fm"]), "-r", str(cfg["rate"]), "-s", "48000",
         "-ow", str(out_wav), str(txt)],
        check=True, capture_output=True)


def read_wav(path):
    with wave.open(str(path)) as w:
        n, rate, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[sw]
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data, rate


def mouth_envelope(samples, rate, duration, fps):
    """フレームごとの口の開き具合(0..1)を音量から作る."""
    n_frames = max(1, int(duration * fps))
    env = np.zeros(n_frames, dtype=np.float32)
    step = rate / fps
    for i in range(n_frames):
        a, b = int(i * step), int((i + 1) * step)
        chunk = samples[a:b]
        if len(chunk):
            env[i] = np.sqrt(np.mean(chunk ** 2))
    peak = env.max() if env.max() > 0 else 1.0
    return np.clip(env / peak * 1.6, 0, 1)


# ---------------------------------------------------------------------------
# 描画ヘルパ
# ---------------------------------------------------------------------------
_font_cache = {}


def font(path, size):
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=fnt) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def outlined_text(d, xy, text, fnt, fill, outline=WHITE, width=4, anchor=None):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width:
                d.text((x + dx, y + dy), text, font=fnt, fill=outline, anchor=anchor)
    d.text((x, y), text, font=fnt, fill=fill, anchor=anchor)


def draw_character(key, mouth, blink, dim):
    """2頭身のオリジナル簡易キャラを RGBA で返す(VOICEVOXの立ち絵ではない)."""
    cw, ch = 300, 300
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    spec = SPEAKERS[key]
    body = spec["body"]
    hair = spec["hair"]
    if dim:  # 聞き手はトーンを落として、話者を目立たせる
        body = tuple(int(c * 0.45 + 252 * 0.55) for c in body)
        hair = tuple(int(c * 0.45 + 252 * 0.55) for c in hair)
    cx = cw // 2
    style = spec.get("style", "twin")
    skin = (255, 240, 228)
    # 後ろ髪(頭より先に描く)
    if style == "twin":     # ツインテール
        for sx in (cx - 124, cx + 68):
            d.rounded_rectangle([sx, 92, sx + 56, 256], radius=28, fill=hair, outline=INK, width=6)
    else:                   # ロングヘア
        d.rounded_rectangle([cx - 106, 90, cx + 106, 246], radius=76, fill=hair, outline=INK, width=6)
    # 体
    d.rounded_rectangle([cx - 74, 186, cx + 74, 300], radius=48, fill=body, outline=INK, width=6)
    # 腕
    d.rounded_rectangle([cx - 104, 208, cx - 62, 276], radius=21, fill=body, outline=INK, width=6)
    d.rounded_rectangle([cx + 62, 208, cx + 104, 276], radius=21, fill=body, outline=INK, width=6)
    # 襟もと(ノアはリボン、メイは襟)
    if style == "twin":
        d.polygon([(cx - 30, 196), (cx, 210), (cx - 30, 224)], fill=YELLOW, outline=INK)
        d.polygon([(cx + 30, 196), (cx, 210), (cx + 30, 224)], fill=YELLOW, outline=INK)
        d.ellipse([cx - 11, 199, cx + 11, 221], fill=YELLOW, outline=INK, width=4)
    else:
        d.polygon([(cx - 44, 190), (cx, 232), (cx + 44, 190)], fill=WHITE, outline=INK)
    # 頭
    d.ellipse([cx - 84, 40, cx + 84, 208], fill=skin, outline=INK, width=6)
    # 前髪(chordは弦の部分にも輪郭線を引いてしまうので、髪色で塗り消す)
    d.chord([cx - 84, 40, cx + 84, 208], 180, 360, fill=hair, outline=INK, width=6)
    d.line([(cx - 80, 124), (cx + 80, 124)], fill=hair, width=10)
    if style == "twin":     # ぱっつん
        d.rectangle([cx - 78, 106, cx + 78, 124], fill=hair)
    else:                   # 斜め分け
        d.ellipse([cx - 90, 62, cx - 10, 132], fill=hair, outline=INK, width=6)
    # 目
    for ex in (cx - 36, cx + 36):
        if blink:
            d.arc([ex - 18, 122, ex + 18, 152], 200, 340, fill=INK, width=6)
        else:
            d.ellipse([ex - 18, 112, ex + 18, 152], fill=INK)
            d.ellipse([ex - 8, 120, ex + 4, 134], fill=WHITE)
            d.ellipse([ex + 2, 138, ex + 9, 145], fill=(255, 255, 255, 200))
    # メガネ(先生役)
    if style == "long":
        for ex in (cx - 36, cx + 36):
            d.ellipse([ex - 26, 110, ex + 26, 156], outline=INK, width=5)
        d.line([cx - 10, 132, cx + 10, 132], fill=INK, width=5)
    # 頬
    d.ellipse([cx - 74, 150, cx - 46, 170], fill=(255, 168, 180))
    d.ellipse([cx + 46, 150, cx + 74, 170], fill=(255, 168, 180))
    # 口(mouth: 0=閉じ 〜 1=大きく開く)
    if mouth < 0.18:
        d.arc([cx - 16, 166, cx + 16, 186], 20, 160, fill=INK, width=5)
    else:
        oh = int(8 + mouth * 26)
        d.ellipse([cx - 16, 168, cx + 16, 168 + oh], fill=(150, 66, 84), outline=INK, width=4)
    return img


def build_char_cache():
    cache = {}
    for key in SPEAKERS:
        for dim in (False, True):
            for blink in (False, True):
                for m in range(4):   # 口の開き 4段階
                    cache[(key, dim, blink, m)] = draw_character(key, m / 3.0, blink, dim)
    return cache


def draw_burst(d, cx, cy, n=26, r0=170, r1=900, color=(255, 236, 190)):
    """集中線."""
    for i in range(n):
        a = 2 * math.pi * i / n
        wdt = 0.055
        pts = [
            (cx + r0 * math.cos(a), cy + r0 * math.sin(a)),
            (cx + r1 * math.cos(a - wdt), cy + r1 * math.sin(a - wdt)),
            (cx + r1 * math.cos(a + wdt), cy + r1 * math.sin(a + wdt)),
        ]
        d.polygon(pts, fill=color)


def scene_background(scene):
    """シーンの静止部分(背景・帯・カード枠)を1枚作る."""
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # 背景のドット模様
    for y in range(0, H, 40):
        for x in range(0, W, 40):
            d.ellipse([x, y, x + 6, y + 6], fill=(240, 232, 214))
    if scene.get("impact"):
        draw_burst(d, W // 2, 250)
    # トップ帯
    d.rounded_rectangle([-30, -40, W + 30, 86], radius=26, fill=YELLOW, outline=INK, width=6)
    vis = scene["visual"]
    outlined_text(d, (44, 18), vis["kicker"], font(FONT_BOLD, 38), INK, WHITE, 3)
    chip = scene.get("chip", "")
    if chip:
        f = font(FONT_BOLD, 28)
        tw = d.textlength(chip, font=f)
        d.rounded_rectangle([W - 44 - tw - 40, 12, W - 44, 68], radius=16, fill=PINK, outline=INK, width=5)
        d.text((W - 44 - tw - 20, 24), chip, font=f, fill=WHITE)
    # メインカード
    d.rounded_rectangle([56, 108, W - 56, 372], radius=30, fill=WHITE, outline=INK, width=6)
    footer = f"{CHANNEL} / {WATERMARK}" if WATERMARK else CHANNEL
    d.text((640, 382), footer, font=font(FONT_REG, 17),
           fill=(170, 160, 145), anchor="ma")
    # 種類別の静止部分
    if vis["type"] == "bullets":
        # カード内(132..352)に必ず収まるよう、はみ出す場合だけ自動で縮める
        top, bottom = 132, 352
        tlines = vis["title"].split("\n")
        ts, tlh, ilh = 46, 56, 48
        need = len(tlines) * tlh + 12 + len(vis["items"]) * ilh
        if need > bottom - top:
            k = (bottom - top) / need
            ts, tlh, ilh = int(ts * k), int(tlh * k), int(ilh * k)
        y = top
        for tl in tlines:
            d.text((92, y), tl, font=font(FONT_BOLD, ts), fill=INK)
            y += tlh
        y += 12
        isize = min(32, ilh - 14)
        for i, it in enumerate(vis["items"]):
            col = [PINK, SKY, PURPLE][i % 3]
            d.rounded_rectangle([92, y + 4, 124, y + 4 + isize], radius=10, fill=col)
            d.text((142, y), it, font=font(FONT_REG, isize), fill=INK)
            y += ilh
    elif vis["type"] == "stat":
        d.text((640, 140), vis["label"], font=font(FONT_BOLD, 32), fill=(120, 118, 130), anchor="ma")
    elif vis["type"] == "bars":
        d.text((92, 128), vis["title"], font=font(FONT_BOLD, 40), fill=INK)
    return img


def draw_visual_anim(img, scene, t):
    """カード内のアニメーション部分(カウントアップ/バー伸長)を重ねる."""
    vis = scene["visual"]
    d = ImageDraw.Draw(img)
    p = min(1.0, t / 0.9)
    p = 1 - (1 - p) ** 3          # ease-out
    if vis["type"] == "stat":
        try:
            target = int(vis["num"])
            shown = str(int(round(target * p)))
        except ValueError:
            shown = vis["num"]
        f = font(FONT_BOLD, 150)
        uf = font(FONT_BOLD, 60)
        tw = d.textlength(shown, font=f)
        uw = d.textlength(vis["unit"], font=uf)
        x = 640 - (tw + uw + 14) / 2
        outlined_text(d, (x, 186), shown, f, PINK, INK, 5)
        outlined_text(d, (x + tw + 14, 268), vis["unit"], uf, INK, WHITE, 3)
    elif vis["type"] == "bars":
        # 本数に応じて行間を詰め、カード内(186..352)に必ず収める
        items = vis["items"]
        y0, y1 = 186, 352
        lh = min(56, (y1 - y0) // max(1, len(items)))
        barh = lh - 14
        fsize = min(30, barh - 4)
        y = y0
        for i, (label, val, total) in enumerate(items):
            col = [PINK, SKY, PURPLE][i % 3]
            d.text((92, y + (barh - fsize) // 2), label, font=font(FONT_REG, fsize), fill=INK)
            bx0, bx1 = 460, 1080
            d.rounded_rectangle([bx0, y, bx1, y + barh], radius=barh // 2, fill=(238, 234, 226))
            wpx = int((bx1 - bx0) * (val / total) * p)
            if wpx > barh:
                d.rounded_rectangle([bx0, y, bx0 + wpx, y + barh], radius=barh // 2, fill=col,
                                    outline=INK, width=4)
            d.text((1100, y + (barh - fsize) // 2), f"{int(round(val * p))}/{total}",
                   font=font(FONT_BOLD, fsize), fill=INK)
            y += lh


BUBBLE_W, BUBBLE_M = 720, 140    # 吹き出し本体の幅 / しっぽ用の左右マージン
BUBBLE_BOTTOM = 612              # 吹き出し本体の下端の画面Y
BUBBLE_TOP_PAD = 22              # 名前タグが本体上端からはみ出す分の余白
BUBBLE_LEFT = {"left": 258, "right": 262}   # 話者別の本体左端X(顔を隠さない位置)
CHAR_X = {"left": -40, "right": 980}        # キャラ立ち位置(300pxスプライトの左上X)
CHAR_Y = 428


def render_bubble(text, speaker):
    """吹き出し(=字幕)を返す。(RGBA画像, 本体の高さ) — 本体左上は (BUBBLE_M, 0)."""
    bw, m, pad = BUBBLE_W, BUBBLE_M, 34
    f = font(FONT_BOLD, 34)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines = wrap(tmp, text, f, bw - pad * 2)
    bh = pad * 2 + 46 * len(lines)
    top = BUBBLE_TOP_PAD          # 名前タグが本体からはみ出す分(切れないように確保)
    img = Image.new("RGBA", (bw + m * 2, top + bh + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    left = SPEAKERS[speaker]["side"] == "left"
    # しっぽ(先に描いて本体で根元を隠す)
    by = top + bh
    if left:
        tail = [(m + 30, by - 20), (m + 110, by - 20), (m - 74, by + 48)]
    else:
        tail = [(m + bw - 110, by - 20), (m + bw - 30, by - 20), (m + bw + 74, by + 48)]
    d.polygon(tail, fill=WHITE)
    d.line([tail[0], tail[2]], fill=INK, width=6)
    d.line([tail[1], tail[2]], fill=INK, width=6)
    # 本体
    d.rounded_rectangle([m, top, m + bw, by], radius=28, fill=WHITE, outline=INK, width=6)
    y = top + pad - 6
    for ln in lines:
        d.text((m + pad, y), ln, font=f, fill=INK)
        y += 46
    # 名前タグ(本体の上端にまたがる)
    nf = font(FONT_BOLD, 24)
    name = SPEAKERS[speaker]["name"]
    nw = d.textlength(name, font=nf)
    nx = m + 40 if left else m + bw - nw - 40
    tag = tuple(int(c * 0.62) for c in SPEAKERS[speaker]["body"])   # 白文字が読める濃さに
    d.rounded_rectangle([nx - 16, top - 20, nx + nw + 16, top + 20], radius=15,
                        fill=tag, outline=INK, width=4)
    d.text((nx, top - 16), name, font=nf, fill=WHITE)
    return img, bh


# ---------------------------------------------------------------------------
# 本体
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", nargs="?", default="build")
    ap.add_argument("--engine", choices=["auto", "voicevox", "openjtalk"], default="auto")
    args = ap.parse_args()

    out = Path(args.outdir)
    audio_dir = out / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    engine = args.engine
    if engine == "auto":
        engine = "voicevox" if voicevox_available() else "openjtalk"
    print(f"[engine] {engine}")
    if engine == "openjtalk":
        print("  ※VOICEVOXエンジン未検出のためOpen JTalkで仮生成します。")
        print("    Mac側でVOICEVOXアプリを起動してから実行すると、ずんだもん等の声になります。")

    # --- 音声生成 ---------------------------------------------------------
    timeline = []      # (scene_idx, line, duration, envelope)
    chapters = []      # (開始秒, 見出し) — YouTubeの概要欄にそのまま貼れる形で出す
    elapsed = 0.0
    all_audio = []
    rate = None
    for si, scene in enumerate(SCENES):
        if "chapter" in scene:
            chapters.append((elapsed, scene["chapter"]))
        for li, line in enumerate(scene["lines"]):
            idx = len(timeline)
            wav = audio_dir / f"l{idx:03d}.wav"
            spec = SPEAKERS[line["sp"]]
            text = line.get("tts", line["text"])
            if engine == "voicevox":
                tts_voicevox(text, spec["voicevox"], wav)
            else:
                tts_openjtalk(text, spec["ojt"], wav)
            samples, rate = read_wav(wav)
            pause = SCENE_PAUSE if li == len(scene["lines"]) - 1 else LINE_PAUSE
            dur = len(samples) / rate + pause
            timeline.append({"scene": si, "line": line, "dur": dur,
                             "env": mouth_envelope(samples, rate, dur, FPS)})
            elapsed += dur
            all_audio.append(samples)
            all_audio.append(np.zeros(int(pause * rate), dtype=np.float32))
        print(f"  tts scene {si + 1}/{len(SCENES)}")

    narration = out / "narration.wav"
    merged = np.concatenate(all_audio)
    peak = np.abs(merged).max() or 1.0
    merged = (merged / peak * 0.89 * 32767).astype(np.int16)
    with wave.open(str(narration), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(merged.tobytes())

    total = sum(t["dur"] for t in timeline)
    print(f"[audio] {total/60:.2f} min / {len(timeline)} lines")

    # チャプターは音声の長さで決まるので、この時点で確定できる
    if chapters:
        lines_out = [f"{int(t) // 60:02d}:{int(t) % 60:02d} {name}" for t, name in chapters]
        (out / "chapters.txt").write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        print(f"[chapters] {len(chapters)}章 -> {out / 'chapters.txt'}")
        for l in lines_out:
            print(f"    {l}")

    # --- 映像生成(ffmpegへ直接パイプ) -----------------------------------
    chars = build_char_cache()
    mp4 = out / "sample_video.mp4"
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", str(narration),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-shortest", str(mp4)],
        stdin=subprocess.PIPE)

    bg_cache, cur_scene, scene_t = None, -1, 0.0
    for ti, item in enumerate(timeline):
        scene = SCENES[item["scene"]]
        if item["scene"] != cur_scene:
            cur_scene = item["scene"]
            bg_cache = scene_background(scene)
            scene_t = 0.0
        bubble, bub_h = render_bubble(item["line"]["text"], item["line"]["sp"])
        speaker = item["line"]["sp"]
        n_frames = max(1, int(round(item["dur"] * FPS)))
        for fi in range(n_frames):
            t = fi / FPS
            frame = bg_cache.copy()
            draw_visual_anim(frame, scene, scene_t + t)
            # キャラ(話者は揺れ+口パク、聞き手はトーンダウン)
            for key in SPEAKERS:
                talking = key == speaker
                m = int(round(item["env"][min(fi, len(item["env"]) - 1)] * 3)) if talking else 0
                blink = (int((scene_t + t) * 1000) % 3400) < 130
                bob = int(math.sin((scene_t + t) * 7.5) * 5) if talking else 0
                sprite = chars[(key, not talking, blink, m)]
                frame.paste(sprite, (CHAR_X[SPEAKERS[key]["side"]], CHAR_Y + bob), sprite)
            # 吹き出し(登場時にポップイン)
            pop = min(1.0, t / 0.16)
            scale = 0.86 + 0.18 * pop - 0.04 * max(0.0, math.sin(pop * math.pi))
            bx = BUBBLE_LEFT[SPEAKERS[speaker]["side"]] - BUBBLE_M
            by = BUBBLE_BOTTOM - bub_h - BUBBLE_TOP_PAD
            if scale < 0.999:
                b = bubble.resize((int(bubble.width * scale), int(bubble.height * scale)),
                                  Image.BILINEAR)
                # 本体の下端を固定したまま縮小(ポップイン時の位置ブレ防止)
                bx += int((bubble.width - b.width) * (0.5 if SPEAKERS[speaker]["side"] == "left" else 0.5))
                by += int(bub_h - bub_h * scale)
            else:
                b = bubble
            frame.paste(b, (bx, by), b)
            proc.stdin.write(frame.tobytes())
        scene_t += item["dur"]
        if (ti + 1) % 20 == 0:
            print(f"  video {ti + 1}/{len(timeline)} lines")

    proc.stdin.close()
    proc.wait()
    render_thumbnail(out / "thumbnail.png")
    print(f"[done] {total/60:.2f} min -> {mp4}")


def render_thumbnail(path):
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    draw_burst(d, 700, 300, n=30, r0=120, r1=1100, color=(255, 226, 168))
    d.rounded_rectangle([-20, -20, W + 20, H + 20], radius=10, outline=INK, width=14)
    outlined_text(d, (58, 40), "時間術の本 15冊の紹介文をAI分析", font(FONT_BOLD, 46), PINK, WHITE, 6)
    outlined_text(d, (58, 122), "共通点", font(FONT_BOLD, 92), INK, WHITE, 8)
    outlined_text(d, (58, 232), "ゼロ", font(FONT_BOLD, 160), PINK, WHITE, 10)
    outlined_text(d, (58, 412), "だった", font(FONT_BOLD, 92), INK, WHITE, 8)
    d.rounded_rectangle([52, 540, 780, 646], radius=24, fill=SKY, outline=INK, width=7)
    outlined_text(d, (80, 558), "紹介文で本を選ぶな", font(FONT_BOLD, 54), WHITE, INK, 4)
    for key, x in (("noa", 890), ("mei", 1120)):
        sp = draw_character(key, 0.7, False, False)
        sp = sp.resize((330, 330), Image.LANCZOS)
        img.paste(sp, (x, 380), sp)
    d.text((W - 40, 30), f"{CHANNEL} #01", font=font(FONT_BOLD, 30), fill=INK, anchor="ra")
    img.save(path)


if __name__ == "__main__":
    main()
