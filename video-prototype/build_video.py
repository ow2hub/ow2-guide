#!/usr/bin/env python3
"""仮動画ビルダー v2 — 漫画風ポップアニメ + キャラ掛け合い + VOICEVOX対応.

「AI実践読書ラボ」第1回:
  『時間術の本30冊をAIに分析させたら、共通点は3つしかなかった』

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
WATERMARK = "仮動画サンプル / 数値はダミー"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
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
    "labo": {   # 生徒・ツッコミ役
        "name": "ラボくん",
        "voicevox": 3,          # ずんだもん
        "ojt": {"fm": 5.0, "rate": 1.05},
        "body": MINT, "hair": (54, 168, 146), "side": "left",
    },
    "mei": {    # 解説・先生役
        "name": "メイ先生",
        "voicevox": 2,          # 四国めたん
        "ojt": {"fm": -1.0, "rate": 1.0},
        "body": PINK, "hair": (206, 78, 118), "side": "right",
    },
}

LINE_PAUSE = 0.28
SCENE_PAUSE = 0.6

# ---------------------------------------------------------------------------
# 台本
#   visual: bullets / stat / bars   impact=True で集中線
#   lines : sp(話者) text(吹き出し表示) tts(読み上げ用/省略時はtext)
# ---------------------------------------------------------------------------
SCENES = [
    # ---- OP フック ---------------------------------------------------------
    {
        "chip": "OP",
        "visual": {"type": "stat", "kicker": "今回の検証", "num": "30", "unit": "冊",
                   "label": "時間術・生産性の本をAIで横断分析"},
        "lines": [
            {"sp": "labo", "text": "先生!時間術の本、30冊も買ったのだ!",
             "tts": "先生!時間術の本、さんじゅっさつも買ったのだ!"},
            {"sp": "mei", "text": "あら偉いわね。それで、全部読んだの?"},
            {"sp": "labo", "text": "…読む前に、AIに分析させたのだ",
             "tts": "読む前に、エーアイに分析させたのだ"},
            {"sp": "mei", "text": "本末転倒だけど、結果はかなり面白かったわね"},
        ],
    },
    {
        "chip": "OP",
        "impact": True,
        "visual": {"type": "stat", "kicker": "30冊に共通していた主張は", "num": "3", "unit": "つ",
                   "label": "…しかも「アレ」は入っていなかった"},
        "lines": [
            {"sp": "mei", "text": "30冊すべてに共通していた主張は、たった3つだったの",
             "tts": "さんじゅっさつすべてに共通していた主張は、たったみっつだったの"},
            {"sp": "labo", "text": "30冊分の共通点が、3つ…!?",
             "tts": "さんじゅっさつぶんの共通点が、みっつ!?"},
            {"sp": "mei", "text": "しかも、あなたが絶対に入ると思ってるアレは、入ってなかったわ"},
            {"sp": "labo", "text": "気になって夜も眠れないのだ!"},
        ],
    },
    # ---- 予告 --------------------------------------------------------------
    {
        "chip": "予告",
        "visual": {"type": "bullets", "kicker": "この動画でわかること",
                   "title": "30冊分析でわかった3つ",
                   "items": ["① 全30冊に共通した主張トップ3",
                             "② 意外にも少数派だった有名テクニック",
                             "③ じゃあ本を読む意味はどこにあるのか"]},
        "lines": [
            {"sp": "mei", "text": "今日わかることは3つよ", "tts": "今日わかることはみっつよ"},
            {"sp": "mei", "text": "1つ目、30冊に共通した主張トップ3",
             "tts": "ひとつめ、さんじゅっさつに共通した主張トップスリー"},
            {"sp": "mei", "text": "2つ目、意外にも少数派だった有名テクニック",
             "tts": "ふたつめ、意外にも少数派だった有名テクニック"},
            {"sp": "mei", "text": "3つ目、じゃあ本を読む意味はどこにあるのか",
             "tts": "みっつめ、じゃあ本を読む意味はどこにあるのか"},
            {"sp": "labo", "text": "最後のやつ、このチャンネルの存在意義が問われるのだ…"},
            {"sp": "mei", "text": "そうね。でも、今日で一番大事な話よ"},
        ],
    },
    # ---- 検証方法(透明性) -------------------------------------------------
    {
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "どうやって分析したか",
                   "title": "使ったのは本文ではない",
                   "items": ["Amazonランキング上位から機械的に30冊",
                             "目次 + 公開されている紹介文 + 自分の読書メモ",
                             "本文の全文はAIに入れていない"]},
        "lines": [
            {"sp": "mei", "text": "まず、どうやって分析したかを正直に話すわ"},
            {"sp": "mei", "text": "Amazonの時間術ランキング上位から、機械的に30冊選んだの",
             "tts": "アマゾンの時間術ランキング上位から、機械的にさんじゅっさつ選んだの"},
            {"sp": "mei", "text": "使ったのは目次と、公開されている紹介文と、私の読書メモだけ"},
            {"sp": "labo", "text": "本文を全部AIに入れちゃダメなのだ?",
             "tts": "本文を全部エーアイに入れちゃダメなのだ?"},
            {"sp": "mei", "text": "著作権的にグレーだからやめておいたわ。ここは正直に言っておくわね"},
            {"sp": "mei", "text": "そこから主張を抜き出して、同じ意味のものをまとめて、数える。それだけよ"},
        ],
    },
    {
        "chip": "検証方法",
        "visual": {"type": "bullets", "kicker": "分析パイプライン",
                   "title": "187個 → 41個に圧縮",
                   "items": ["抽出できた主張: 187個",
                             "同じ意味を統合したユニーク主張: 41個",
                             "20冊以上に登場したもの: たった3個"]},
        "lines": [
            {"sp": "mei", "text": "抽出できた主張は、全部で187個",
             "tts": "抽出できた主張は、全部でひゃくはちじゅうななこ"},
            {"sp": "mei", "text": "同じ意味のものを統合したら、41個まで減ったわ",
             "tts": "同じ意味のものを統合したら、よんじゅういっこまで減ったわ"},
            {"sp": "labo", "text": "30冊で41個…けっこう被ってるのだ",
             "tts": "さんじゅっさつでよんじゅういっこ。けっこう被ってるのだ"},
            {"sp": "mei", "text": "そう。そのうち20冊以上に登場したのは、この3つだけ",
             "tts": "そう。そのうちにじゅっさつ以上に登場したのは、このみっつだけ"},
        ],
    },
    # ---- POINT 1 -----------------------------------------------------------
    {
        "chip": "POINT 1/3",
        "visual": {"type": "bars", "kicker": "POINT 1 — 共通点トップ3",
                   "title": "30冊中、何冊が言っていたか",
                   "items": [("やらないことを決める", 24, 30),
                             ("重要と緊急を分ける", 22, 30),
                             ("似た作業はまとめて処理", 21, 30)]},
        "lines": [
            {"sp": "mei", "text": "第1位、やらないことを決める。30冊中24冊",
             "tts": "だいいちい、やらないことを決める。さんじゅっさつちゅう、にじゅうよんさつ"},
            {"sp": "mei", "text": "第2位、重要と緊急を分ける。22冊",
             "tts": "だいにい、重要と緊急を分ける。にじゅうにさつ"},
            {"sp": "mei", "text": "第3位、似た作業はまとめて処理する。21冊",
             "tts": "だいさんい、似た作業はまとめて処理する。にじゅういっさつ"},
            {"sp": "labo", "text": "…どれも聞いたことあるやつなのだ"},
            {"sp": "mei", "text": "そうなの。つまりこの3つは、もう常識になってるってことね",
             "tts": "そうなの。つまりこのみっつは、もう常識になってるってことね"},
            {"sp": "mei", "text": "逆に言えば、ここだけなら本を買わなくても手に入るわ"},
        ],
    },
    {
        "chip": "POINT 1/3",
        "visual": {"type": "bullets", "kicker": "POINT 1 — 言い方が違うだけ",
                   "title": "同じことを30通りで言っている",
                   "items": ["『エッセンシャル思考』→ 90点ルール",
                             "『7つの習慣』→ 第2領域に時間を使う",
                             "どちらも中身は「取捨選択」"]},
        "lines": [
            {"sp": "mei", "text": "1位の「やらないことを決める」は、本によって言い方が違うだけなの",
             "tts": "いちいの、やらないことを決めるは、本によって言い方が違うだけなの"},
            {"sp": "mei", "text": "エッセンシャル思考なら90点ルール、7つの習慣なら第2領域",
             "tts": "エッセンシャル思考ならきゅうじゅってんルール、ななつの習慣ならだいにりょういき"},
            {"sp": "mei", "text": "言葉は違うけど、やってることは同じ。取捨選択よ"},
            {"sp": "labo", "text": "30冊読んでやっと気づくやつなのだ…",
             "tts": "さんじゅっさつ読んでやっと気づくやつなのだ"},
            {"sp": "mei", "text": "だから「1冊で十分」とも言えるし…"},
            {"sp": "mei", "text": "「言い方が30通りあるから、自分に刺さる1つを探せ」とも言えるわね",
             "tts": "言い方がさんじゅうどおりあるから、自分に刺さるひとつを探せ、とも言えるわね"},
        ],
    },
    # ---- POINT 2(中盤の驚き) ---------------------------------------------
    {
        "chip": "POINT 2/3",
        "impact": True,
        "visual": {"type": "bars", "kicker": "POINT 2 — 意外な少数派",
                   "title": "有名テクニックは何冊?",
                   "items": [("早起き", 8, 30), ("朝活", 6, 30), ("ポモドーロ", 9, 30)]},
        "lines": [
            {"sp": "labo", "text": "ところで先生、「早起き」は何位だったのだ?"},
            {"sp": "mei", "text": "30冊中、8冊よ", "tts": "さんじゅっさつちゅう、はっさつよ"},
            {"sp": "labo", "text": "えっ、たった8冊!?", "tts": "えっ、たったはっさつ!?"},
            {"sp": "mei", "text": "朝活にいたっては6冊。ポモドーロも9冊だったわ",
             "tts": "朝活にいたってはろくさつ。ポモドーロもきゅうさつだったわ"},
            {"sp": "labo", "text": "時間術といえば早起き、じゃなかったのだ…?"},
            {"sp": "mei", "text": "それ、たぶん本じゃなくてSNSで刷り込まれたイメージね",
             "tts": "それ、たぶん本じゃなくて、エスエヌエスで刷り込まれたイメージね"},
            {"sp": "mei", "text": "有名なテクニックほど、実は少数派だった。これが一番の発見よ"},
        ],
    },
    # ---- POINT 3 -----------------------------------------------------------
    {
        "chip": "POINT 3/3",
        "visual": {"type": "stat", "kicker": "POINT 3 — 差分にこそ価値がある",
                   "num": "19", "unit": "個",
                   "label": "41個中、1冊にしか出てこなかった主張"},
        "lines": [
            {"sp": "mei", "text": "最後よ。1冊にしか出てこなかった主張が、19個あったの",
             "tts": "最後よ。いっさつにしか出てこなかった主張が、じゅうきゅうこあったの"},
            {"sp": "labo", "text": "41個中19個が、その本だけのオリジナル…!",
             "tts": "よんじゅういっこちゅう、じゅうきゅうこが、その本だけのオリジナル!"},
            {"sp": "mei", "text": "そう。ここが今回、一番面白かったところ"},
            {"sp": "mei", "text": "共通の3つは、どの本にも書いてある。つまり要約で済む部分よ",
             "tts": "共通のみっつは、どの本にも書いてある。つまり要約で済む部分よ"},
            {"sp": "mei", "text": "でも本当の価値は、その本にしかない19個のほうにあるの",
             "tts": "でも本当の価値は、その本にしかない、じゅうきゅうこのほうにあるの"},
            {"sp": "labo", "text": "要約だけ見てたら、そこは絶対に手に入らないのだ…"},
        ],
    },
    {
        "chip": "POINT 3/3",
        "visual": {"type": "bullets", "kicker": "19個の中で一番刺さったもの",
                   "title": "予定表に「やらないこと」を書く",
                   "items": ["カレンダーに「何もしない時間」を先に入れる",
                             "登場は30冊中わずか1冊",
                             "共通点にはならない。でも刺さる人には刺さる"]},
        "lines": [
            {"sp": "mei", "text": "ちなみに19個の中で、私に一番刺さったのはこれ",
             "tts": "ちなみにじゅうきゅうこの中で、私に一番刺さったのはこれ"},
            {"sp": "mei", "text": "カレンダーに「この時間は何もしない」と先に書く、という主張ね"},
            {"sp": "labo", "text": "それ、1冊にしか書いてないのだ?", "tts": "それ、いっさつにしか書いてないのだ?"},
            {"sp": "mei", "text": "ええ。でも私はこれで一番救われたわ"},
            {"sp": "mei", "text": "共通点にはならない。でも刺さる人には刺さる。それが本の価値よ"},
            {"sp": "labo", "text": "要約は地図で、本は現地ってことなのだ!"},
            {"sp": "mei", "text": "いいこと言うわね。まさにそれよ"},
        ],
    },
    # ---- 限界の開示 --------------------------------------------------------
    {
        "chip": "正直な話",
        "visual": {"type": "bullets", "kicker": "この分析の限界",
                   "title": "数字は「目安」として見てほしい",
                   "items": ["選書はランキング順 → 名著が漏れている可能性",
                             "AIのタグ付けはブレる → 3回実行し2回以上一致のみ採用",
                             "本文全文は未使用のため取りこぼしがある"]},
        "lines": [
            {"sp": "mei", "text": "もちろん、この分析には限界があるわ"},
            {"sp": "mei", "text": "選書はランキング順だから、名著が漏れている可能性がある"},
            {"sp": "mei", "text": "AIのタグ付けもブレるから、3回実行して2回以上一致したものだけ採用したの",
             "tts": "エーアイのタグ付けもブレるから、さんかい実行して、にかい以上一致したものだけ採用したの"},
            {"sp": "labo", "text": "それでもブレたのだ?"},
            {"sp": "mei", "text": "ええ。だから数字は目安として見てちょうだい"},
        ],
    },
    # ---- まとめ + 次回 -----------------------------------------------------
    {
        "chip": "まとめ",
        "visual": {"type": "bullets", "kicker": "今日のまとめ",
                   "title": "30冊分析の結論",
                   "items": ["共通点はたった3つ。ここは要約で足りる",
                             "有名テクニックほど実は少数派だった",
                             "本の価値は「その本にしかない差分」にある"]},
        "lines": [
            {"sp": "mei", "text": "まとめるわ。共通点は3つだけ、有名テクは少数派、価値は差分にある",
             "tts": "まとめるわ。共通点はみっつだけ、有名テクは少数派、価値は差分にある"},
            {"sp": "labo", "text": "今日から何をすればいいのだ?"},
            {"sp": "mei", "text": "まず「やらないこと」を3つ書き出すこと",
             "tts": "まず、やらないことを、みっつ書き出すこと"},
            {"sp": "mei", "text": "24冊が言ってるんだから、たぶん本当よ",
             "tts": "にじゅうよんさつが言ってるんだから、たぶん本当よ"},
            {"sp": "labo", "text": "みんなは何を「やらない」ことにするのだ? コメントで教えてほしいのだ!"},
        ],
    },
    {
        "chip": "次回予告",
        "visual": {"type": "bullets", "kicker": "次回予告",
                   "title": "41個の主張をAIに全部やらせる",
                   "items": ["本の教えを、AIで実行可能にする",
                             "毎週金曜 19時 更新",
                             "チャンネル登録で次回の検証をお見逃しなく"]},
        "lines": [
            {"sp": "mei", "text": "次回は、この41個の主張をAIエージェントに全部やらせてみるわ",
             "tts": "次回は、このよんじゅういっこの主張を、エーアイエージェントに全部やらせてみるわ"},
            {"sp": "labo", "text": "本の教えを、AIで実行可能にするチャンネルなのだ!",
             "tts": "本の教えを、エーアイで実行可能にするチャンネルなのだ!"},
            {"sp": "mei", "text": "気に入ったらチャンネル登録をお願いね"},
            {"sp": "labo", "text": "それじゃ、また次の動画で会うのだ!"},
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
    # 体
    d.rounded_rectangle([cx - 74, 186, cx + 74, 300], radius=48, fill=body, outline=INK, width=6)
    # 腕
    d.rounded_rectangle([cx - 104, 208, cx - 62, 276], radius=21, fill=body, outline=INK, width=6)
    d.rounded_rectangle([cx + 62, 208, cx + 104, 276], radius=21, fill=body, outline=INK, width=6)
    # 頭
    d.ellipse([cx - 84, 40, cx + 84, 208], fill=(255, 240, 226), outline=INK, width=6)
    # 髪
    d.chord([cx - 84, 40, cx + 84, 208], 180, 360, fill=hair, outline=INK, width=6)
    if spec["side"] == "left":
        d.ellipse([cx - 104, 60, cx - 52, 130], fill=hair, outline=INK, width=6)   # アホ毛風
    else:
        d.ellipse([cx + 56, 78, cx + 108, 190], fill=hair, outline=INK, width=6)   # サイドヘア
        d.ellipse([cx - 108, 78, cx - 56, 190], fill=hair, outline=INK, width=6)
    # 目
    for ex in (cx - 36, cx + 36):
        if blink:
            d.line([ex - 17, 132, ex + 17, 132], fill=INK, width=6)
        else:
            d.ellipse([ex - 17, 112, ex + 17, 150], fill=INK)
            d.ellipse([ex - 7, 120, ex + 3, 132], fill=WHITE)
    # 頬
    d.ellipse([cx - 72, 148, cx - 46, 166], fill=(255, 170, 180))
    d.ellipse([cx + 46, 148, cx + 72, 166], fill=(255, 170, 180))
    # 口(mouth: 0=閉じ 〜 1=大きく開く)
    if mouth < 0.18:
        d.line([cx - 14, 172, cx + 14, 172], fill=INK, width=5)
    else:
        oh = int(8 + mouth * 26)
        d.ellipse([cx - 16, 166, cx + 16, 166 + oh], fill=(120, 52, 68), outline=INK, width=4)
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
    d.text((640, 382), f"{CHANNEL} / {WATERMARK}", font=font(FONT_REG, 17),
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
        y = 192
        for i, (label, val, total) in enumerate(vis["items"]):
            col = [PINK, SKY, PURPLE][i % 3]
            d.text((92, y + 4), label, font=font(FONT_REG, 30), fill=INK)
            bx0, bx1 = 460, 1080
            d.rounded_rectangle([bx0, y, bx1, y + 42], radius=21, fill=(238, 234, 226))
            wpx = int((bx1 - bx0) * (val / total) * p)
            if wpx > 12:
                d.rounded_rectangle([bx0, y, bx0 + wpx, y + 42], radius=21, fill=col,
                                    outline=INK, width=4)
            d.text((1100, y + 4), f"{int(round(val * p))}/{total}",
                   font=font(FONT_BOLD, 30), fill=INK)
            y += 56


BUBBLE_W, BUBBLE_M = 720, 140    # 吹き出し本体の幅 / しっぽ用の左右マージン
BUBBLE_BOTTOM = 612              # 吹き出し本体の下端の画面Y
BUBBLE_LEFT = {"left": 210, "right": 270}   # 話者別の本体左端X(顔を隠さない位置)
CHAR_X = {"left": -40, "right": 980}        # キャラ立ち位置(300pxスプライトの左上X)
CHAR_Y = 428


def render_bubble(text, speaker):
    """吹き出し(=字幕)を返す。(RGBA画像, 本体の高さ) — 本体左上は (BUBBLE_M, 0)."""
    bw, m, pad = BUBBLE_W, BUBBLE_M, 34
    f = font(FONT_BOLD, 34)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    lines = wrap(tmp, text, f, bw - pad * 2)
    bh = pad * 2 + 46 * len(lines)
    img = Image.new("RGBA", (bw + m * 2, bh + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    left = SPEAKERS[speaker]["side"] == "left"
    # しっぽ(先に描いて本体で根元を隠す)
    if left:
        tail = [(m + 30, bh - 20), (m + 110, bh - 20), (m - 74, bh + 48)]
    else:
        tail = [(m + bw - 110, bh - 20), (m + bw - 30, bh - 20), (m + bw + 74, bh + 48)]
    d.polygon(tail, fill=WHITE)
    d.line([tail[0], tail[2]], fill=INK, width=6)
    d.line([tail[1], tail[2]], fill=INK, width=6)
    # 本体
    d.rounded_rectangle([m, 0, m + bw, bh], radius=28, fill=WHITE, outline=INK, width=6)
    y = pad - 6
    for ln in lines:
        d.text((m + pad, y), ln, font=f, fill=INK)
        y += 46
    # 名前タグ
    nf = font(FONT_BOLD, 24)
    name = SPEAKERS[speaker]["name"]
    nw = d.textlength(name, font=nf)
    nx = m + 40 if left else m + bw - nw - 40
    d.rounded_rectangle([nx - 16, -16, nx + nw + 16, 22], radius=14,
                        fill=SPEAKERS[speaker]["body"], outline=INK, width=4)
    d.text((nx, -12), name, font=nf, fill=WHITE)
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
    all_audio = []
    rate = None
    for si, scene in enumerate(SCENES):
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
            for key in ("labo", "mei"):
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
            by = BUBBLE_BOTTOM - bub_h
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
    outlined_text(d, (58, 40), "時間術の本 30冊をAI分析", font(FONT_BOLD, 50), PINK, WHITE, 6)
    outlined_text(d, (58, 130), "共通点は", font(FONT_BOLD, 92), INK, WHITE, 8)
    outlined_text(d, (58, 240), "3つだけ", font(FONT_BOLD, 150), PINK, WHITE, 10)
    outlined_text(d, (58, 410), "だった", font(FONT_BOLD, 92), INK, WHITE, 8)
    d.rounded_rectangle([52, 540, 720, 646], radius=24, fill=SKY, outline=INK, width=7)
    outlined_text(d, (80, 558), "「早起き」は入ってない", font(FONT_BOLD, 54), WHITE, INK, 4)
    for key, x in (("labo", 900), ("mei", 1120)):
        sp = draw_character(key, 0.7, False, False)
        sp = sp.resize((330, 330), Image.LANCZOS)
        img.paste(sp, (x, 380), sp)
    d.text((W - 40, 30), f"{CHANNEL} #01", font=font(FONT_BOLD, 30), fill=INK, anchor="ra")
    img.save(path)


if __name__ == "__main__":
    main()
