#!/usr/bin/env python3
"""仮動画ビルダー — 「本×AI×実践検証」チャンネル 第1回プロトタイプ.

台本データ(SCENES)からスライド画像(Pillow)・ナレーション(Open JTalk)を生成し、
ffmpeg で字幕焼き込みの MP4 に組み立てる。サムネイル案も出力する。

必要パッケージ: ffmpeg, open-jtalk, open-jtalk-mecab-naist-jdic,
                hts-voice-nitech-jp-atr503-m001, fonts-noto-cjk, pillow

使い方: python3 build_video.py <出力ディレクトリ>
"""

import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (14, 23, 38)          # ダークネイビー
BG_PANEL = (22, 35, 58)
ACCENT = (245, 185, 66)    # アンバー
TEXT = (240, 243, 248)
SUBTEXT = (168, 180, 198)
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
DIC = "/var/lib/mecab/dic/open-jtalk/naist-jdic"
VOICE = "/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice"
CHANNEL = "AI実践読書ラボ"
WATERMARK = "仮動画サンプル(音声・数値はダミー)"
LINE_PAUSE = 0.35   # 行間ポーズ(秒)
SCENE_PAUSE = 0.7   # シーン間ポーズ(秒)

# ---------------------------------------------------------------------------
# 台本データ
# 各シーン: slide(kicker/title/bullets/chip) + lines(text=字幕, tts=読み上げ用)
# ---------------------------------------------------------------------------
SCENES = [
    # ---- 0:00 フック -------------------------------------------------------
    {
        "slide": {
            "kicker": "本 × AI × 実践検証 #01",
            "title": "『エッセンシャル思考』を\nAIに1週間任せてみた",
            "bullets": ["会議が4本消えた", "退社が平均50分早くなった", "ただし大失敗が1つ…"],
            "chip": "OP",
        },
        "lines": [
            {"text": "ベストセラー『エッセンシャル思考』。その教えを、AIに丸ごと任せて1週間働いてみました。",
             "tts": "ベストセラー、エッセンシャル思考。その教えを、エーアイに丸ごと任せて、一週間働いてみました。"},
            {"text": "結果、会議は4本消えて、退社時間は平均でおよそ50分早くなりました。",
             "tts": "結果、会議は四本消えて、退社時間は平均で、およそ五十分早くなりました。"},
            {"text": "ただし、1つだけ大きな失敗もしました。それは動画の後半でお話しします。",
             "tts": "ただし、ひとつだけ大きな失敗もしました。それは動画の後半でお話しします。"},
        ],
    },
    # ---- 0:30 予告+自己紹介 ------------------------------------------------
    {
        "slide": {
            "kicker": "この動画でわかること",
            "title": "本の教えをAIで実行する\n3つの方法",
            "bullets": ["① 90点ルールでタスクを自動仕分け",
                        "② 予定に自動でバッファを入れる",
                        "③ AIに「上手な断り方」を書かせる"],
            "chip": "予告",
        },
        "lines": [
            {"text": "この動画では、本の教えをAIで実行する方法を、3つに絞って紹介します。",
             "tts": "この動画では、本の教えをエーアイで実行する方法を、三つに絞って紹介します。"},
            {"text": "1つ目、90点ルールでタスクを自動で仕分ける。",
             "tts": "ひとつめ、九十点ルールで、タスクを自動で仕分ける。"},
            {"text": "2つ目、予定に自動でバッファ、つまり余白を入れる。",
             "tts": "ふたつめ、予定に自動でバッファ、つまり余白を入れる。"},
            {"text": "3つ目、AIに「上手な断り方」を書かせる。",
             "tts": "みっつめ、エーアイに、上手な断り方を書かせる。"},
            {"text": "申し遅れました。ふだんはIT企業で働きながら、本とAIの組み合わせを検証している、当ラボのナビゲーターです。",
             "tts": "申し遅れました。ふだんはアイティー企業で働きながら、本とエーアイの組み合わせを検証している、当ラボのナビゲーターです。"},
            {"text": "机上の空論ではなく、実際に1週間やってみた記録でお届けします。それでは行きましょう。",
             "tts": "机上の空論ではなく、実際に一週間やってみた記録でお届けします。それでは行きましょう。"},
        ],
    },
    # ---- 1:00 ポイント① 90点ルール -----------------------------------------
    {
        "slide": {
            "kicker": "POINT 1 — 90点ルール",
            "title": "「より少なく、\nしかしより良く」",
            "bullets": ["選択肢は90点以上かで判断する",
                        "90点未満は0点と同じ = やらない",
                        "…でも人間にはこれが難しい"],
            "chip": "POINT 1/3",
        },
        "lines": [
            {"text": "まず1つ目。エッセンシャル思考の核心は、「より少なく、しかしより良く」です。",
             "tts": "まずひとつめ。エッセンシャル思考の核心は、より少なく、しかしより良く、です。"},
            {"text": "著者のグレッグ・マキューンさんは、選択肢を「90点以上かどうか」で判断しろ、と言います。",
             "tts": "著者のグレッグ、マキューンさんは、選択肢を、九十点以上かどうかで判断しろ、と言います。"},
            {"text": "90点未満は、全部0点と同じ。つまり、やらない。",
             "tts": "九十点未満は、全部零点と同じ。つまり、やらない。"},
            {"text": "正直、これ、頭では分かっていても、人間には難しいんですよね。"},
            {"text": "目の前の依頼には、つい「はい」と言ってしまう。私もそうでした。"},
            {"text": "そこで私は、この判断そのものを、AIに外注しました。",
             "tts": "そこで私は、この判断そのものを、エーアイに外注しました。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 1 — やり方",
            "title": "AIを「時間の門番」にする",
            "bullets": ["最初に今期の目標と判断基準を登録",
                        "依頼が来たら内容を貼り付けるだけ",
                        "貢献度を100点満点で採点 → 90点未満は却下"],
            "chip": "POINT 1/3",
        },
        "lines": [
            {"text": "やり方はシンプルです。自分の今期の目標と、判断基準を、最初にAIに登録しておきます。",
             "tts": "やり方はシンプルです。自分の今期の目標と、判断基準を、最初にエーアイに登録しておきます。"},
            {"text": "新しいタスクや依頼が来たら、内容をそのままAIに貼り付けます。",
             "tts": "新しいタスクや依頼が来たら、内容をそのままエーアイに貼り付けます。"},
            {"text": "するとAIが、目標への貢献度を100点満点で採点して、90点未満なら「やらない」と返してくる。",
             "tts": "するとエーアイが、目標への貢献度を百点満点で採点して、九十点未満なら、やらない、と返してくる。"},
            {"text": "ポイントは、AIに「あなたは私の時間の門番です」という役割を与えることです。",
             "tts": "ポイントは、エーアイに、あなたは私の時間の門番です、という役割を与えることです。"},
            {"text": "人間だと情が入ってしまう判断も、門番AIは容赦なく落としてくれます。",
             "tts": "人間だと情が入ってしまう判断も、門番エーアイは容赦なく落としてくれます。"},
            {"text": "例えば「他部署の資料レビュー依頼」。門番の採点は35点。理由は「あなたの目標のどれにも直結しない」。",
             "tts": "例えば、他部署の資料レビュー依頼。門番の採点は三十五点。理由は、あなたの目標のどれにも直結しない。"},
            {"text": "人間の私なら、確実に引き受けていた案件です。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 1 — 検証結果(1週間)",
            "title": "42件中、90点超えは\nたったの9件",
            "bullets": ["判定にかけたタスク: 42件",
                        "90点以上: 9件(約2割)",
                        "= 仕事の8割は「やらなくていいこと」だった"],
            "chip": "POINT 1/3",
        },
        "lines": [
            {"text": "1週間で門番AIに判定させたタスクは、全部で42件。",
             "tts": "一週間で門番エーアイに判定させたタスクは、全部で四十二件。"},
            {"text": "そのうち、90点を超えたのは、たったの9件でした。",
             "tts": "そのうち、九十点を超えたのは、たったの九件でした。"},
            {"text": "つまり、私の仕事の8割は、本の基準では「やらなくていいこと」だったわけです。",
             "tts": "つまり、私の仕事の八割は、本の基準では、やらなくていいことだったわけです。"},
            {"text": "これは正直、ショックでした。でも、空いた時間をどう守るか。ここからが本番です。"},
        ],
    },
    # ---- 4:30 ポイント② バッファ -------------------------------------------
    {
        "slide": {
            "kicker": "POINT 2 — バッファ設計",
            "title": "見積もりは全部1.5倍にする",
            "bullets": ["人間は「計画錯誤」で必ず短く見積もる",
                        "本のルール: 所要時間 × 1.5",
                        "カレンダー登録をAI経由に変えた"],
            "chip": "POINT 2/3",
        },
        "lines": [
            {"text": "2つ目のポイントは、バッファ、つまり余白の設計です。",
             "tts": "ふたつめのポイントは、バッファ、つまり余白の設計です。"},
            {"text": "本には、「見積もり時間を1.5倍にしろ」というルールが出てきます。",
             "tts": "本には、見積もり時間を一点五倍にしろ、というルールが出てきます。"},
            {"text": "人間には「計画錯誤」という癖があって、作業時間をいつも短く見積もってしまうからです。"},
            {"text": "分かっちゃいるけど、手帳の上では今日も自分を過信する。それが人間です。"},
            {"text": "そこで今回は、カレンダーへの予定登録を、すべてAI経由に変えました。",
             "tts": "そこで今回は、カレンダーへの予定登録を、すべてエーアイ経由に変えました。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 2 — やり方",
            "title": "予定は文章で送るだけ",
            "bullets": ["「資料作成 1時間」と送る",
                        "→ 90分の枠 + 直後に15分の予備枠",
                        "移動時間・休憩も自動で追加"],
            "chip": "POINT 2/3",
        },
        "lines": [
            {"text": "予定を文章でAIに送ると、所要時間を1.5倍にして、前後に移動時間と休憩を足した形に整えてくれます。",
             "tts": "予定を文章でエーアイに送ると、所要時間を一点五倍にして、前後に移動時間と休憩を足した形に整えてくれます。"},
            {"text": "例えば「資料作成、1時間」と送ると、90分の枠と、直後に15分の予備枠が入ります。",
             "tts": "例えば、資料作成、一時間、と送ると、九十分の枠と、直後に十五分の予備枠が入ります。"},
            {"text": "最初の2日間は、カレンダーがスカスカに見えて、正直かなり不安になります。",
             "tts": "最初の二日間は、カレンダーがスカスカに見えて、正直かなり不安になります。"},
            {"text": "「こんなに余白を取って、仕事が回るのか?」と。"},
            {"text": "でも、ここで面白いことが起きました。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 2 — 驚きの結果",
            "title": "1.5倍見積もりの的中率は\nほぼ100%だった",
            "bullets": ["時間内に終わらなかったタスク: 42件中3件",
                        "= 今までの締め切りは「自分への嘘」",
                        "余白のおかげで突発対応も余裕に"],
            "chip": "POINT 2/3",
        },
        "lines": [
            {"text": "1週間の記録を取ると、1.5倍にした見積もりは、ほぼぴったり当たっていたんです。",
             "tts": "一週間の記録を取ると、一点五倍にした見積もりは、ほぼぴったり当たっていたんです。"},
            {"text": "42件中、時間内に終わらなかったタスクは3件だけ。",
             "tts": "四十二件中、時間内に終わらなかったタスクは三件だけ。"},
            {"text": "つまり今までの私は、毎日、自分に嘘の締め切りを並べていたことになります。"},
            {"text": "さらに副作用として、予定が減った分、突発の相談を受ける余裕ができました。"},
            {"text": "本の中で一番地味なルールが、検証では一番効きました。これは意外でした。"},
            {"text": "ちなみに皆さんは、自分の見積もりが何倍ずれてるか、測ったことありますか? よければコメントで教えてください。"},
        ],
    },
    # ---- 8:00 ポイント③ 断り方 ---------------------------------------------
    {
        "slide": {
            "kicker": "POINT 3 — 断る技術",
            "title": "断り文は全部AIに\n下書きさせる",
            "bullets": ["本の教え:「きっぱりと、優雅に断る」",
                        "でも断り文を考える時間がもうストレス",
                        "→ 下書きはAIの仕事にする"],
            "chip": "POINT 3/3",
        },
        "lines": [
            {"text": "3つ目は、多くの人が一番苦手なやつ。「断る」です。",
             "tts": "みっつめは、多くの人が一番苦手なやつ。断る、です。"},
            {"text": "本では、「きっぱりと、しかし優雅に断る」ことが大事だとされています。"},
            {"text": "とはいえ、断りの文面を考える時間そのものが、もうストレスですよね。"},
            {"text": "なので、断りのメール文は、全部AIに下書きさせることにしました。",
             "tts": "なので、断りのメール文は、全部エーアイに下書きさせることにしました。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 3 — テンプレの型",
            "title": "「感謝 → 理由 → 代替案」\nを3行で",
            "bullets": ["渡す情報: 相手との関係 / 依頼内容 / 本当の理由",
                        "書かせる型: 感謝・理由・代替案の3行",
                        "代替案が自動で入るのが最大のメリット"],
            "chip": "POINT 3/3",
        },
        "lines": [
            {"text": "プロンプトの型はこうです。相手との関係、依頼の内容、断る本当の理由。この3つを渡す。",
             "tts": "プロンプトの型はこうです。相手との関係、依頼の内容、断る本当の理由。この三つを渡す。"},
            {"text": "そして、「感謝、理由、代替案」の順で、3行以内で書かせる。",
             "tts": "そして、感謝、理由、代替案の順で、三行以内で書かせる。"},
            {"text": "代替案まで自動で入るのが、AIを使う最大のメリットです。",
             "tts": "代替案まで自動で入るのが、エーアイを使う最大のメリットです。"},
            {"text": "例えば、「今週は難しいのですが、来週火曜なら30分お話しできます」のような形ですね。",
             "tts": "例えば、今週は難しいのですが、来週火曜なら三十分お話しできます、のような形ですね。"},
            {"text": "ゼロから断り文を書くのと、下書きを直すのとでは、心理的な負担が全然違います。"},
        ],
    },
    {
        "slide": {
            "kicker": "POINT 3 — 使ってみた結果",
            "title": "1週間で6回断って、\n関係は壊れなかった",
            "bullets": ["断った依頼: 6件(うち5件は下書きほぼそのまま)",
                        "会議も4本辞退 → 人間関係は無事",
                        "今日やること: 断り文の型をAIに登録"],
            "chip": "POINT 3/3",
        },
        "lines": [
            {"text": "この1週間で、依頼を断ったのは6回。",
             "tts": "この一週間で、依頼を断ったのは六回。"},
            {"text": "うち5回は、AIの下書きほぼそのままで、角が立たない文章でした。",
             "tts": "うち五回は、エーアイの下書きほぼそのままで、角が立たない文章でした。"},
            {"text": "会議も、門番AIの判定を理由に4本辞退しましたが、人間関係は今のところ壊れていません。",
             "tts": "会議も、門番エーアイの判定を理由に四本辞退しましたが、人間関係は今のところ壊れていません。"},
            {"text": "今日からできるアクションとしては、まず断り文の型だけでも、AIに登録しておくのがおすすめです。",
             "tts": "今日からできるアクションとしては、まず断り文の型だけでも、エーアイに登録しておくのがおすすめです。"},
            {"text": "今回使ったプロンプトは、3つとも概要欄に置いておきます。",
             "tts": "今回使ったプロンプトは、三つとも概要欄に置いておきます。"},
        ],
    },
    # ---- 11:30 失敗談+本への批評 -------------------------------------------
    {
        "slide": {
            "kicker": "冒頭で予告した話",
            "title": "大失敗:AIを信じすぎた",
            "bullets": ["低得点の依頼を機械的に断った",
                        "→ 実は上司が温めていた企画の相談だった",
                        "AIは「文脈の外の価値」をまだ読めない"],
            "chip": "本音",
        },
        "lines": [
            {"text": "さて、冒頭で予告した、大失敗の話です。"},
            {"text": "門番AIを信じすぎて、ある依頼を機械的に断ったんですが…",
             "tts": "門番エーアイを信じすぎて、ある依頼を機械的に断ったんですが。"},
            {"text": "それが実は、上司が数ヶ月温めていた新企画の、最初の相談だったんです。"},
            {"text": "採点すれば低い。でも、関係としては最重要。AIは、文脈の外にある価値をまだ読めません。",
             "tts": "採点すれば低い。でも、関係としては最重要。エーアイは、文脈の外にある価値を、まだ読めません。"},
            {"text": "翌日、廊下で謝り倒しました。皆さんは同じ失敗をしないでください。"},
            {"text": "なので結論。AIに任せていいのは「判断の下書き」まで。最終判断は、人間の仕事です。",
             "tts": "なので結論。エーアイに任せていいのは、判断の下書きまで。最終判断は、人間の仕事です。"},
        ],
    },
    {
        "slide": {
            "kicker": "まとめ — 本への正直な評価",
            "title": "『エッセンシャル思考』は\nAI時代にこそ効く",
            "bullets": ["「何をやらないか」を決める本として今も最高",
                        "ただし「実行」の部分は自分でAI化が必要",
                        "90点ルール / 1.5倍バッファ / 優雅な断り"],
            "chip": "まとめ",
        },
        "lines": [
            {"text": "最後に、本への正直な評価です。"},
            {"text": "エッセンシャル思考は、「何をやらないか」を決める本としては、今でも最高の一冊だと思います。"},
            {"text": "一方で、書かれた時代にAIはなかったので、「減らした後にどう実行するか」は、今なら自分でアップデートする必要があります。",
             "tts": "一方で、書かれた時代にエーアイはなかったので、減らした後にどう実行するかは、今なら自分でアップデートする必要があります。"},
            {"text": "そこを補うのが、このチャンネル「AI実践読書ラボ」の役目です。",
             "tts": "そこを補うのが、このチャンネル、エーアイ実践読書ラボの役目です。"},
            {"text": "本編で紹介した数字や手順の詳細も、概要欄にまとめてあります。気になる方は本もぜひ読んでみてください。"},
        ],
    },
    # ---- 13:00 CTA ---------------------------------------------------------
    {
        "slide": {
            "kicker": "次回予告",
            "title": "『7つの習慣』の週間計画を\nAIエージェントに1ヶ月運用させる",
            "bullets": ["本の教えを、AIで実行可能にする",
                        "毎週金曜 19時 更新",
                        "チャンネル登録で次回の検証をお見逃しなく"],
            "chip": "次回",
        },
        "lines": [
            {"text": "次回は、『7つの習慣』の週間計画を、AIエージェントに1ヶ月運用させた結果を公開します。",
             "tts": "次回は、七つの習慣の週間計画を、エーアイエージェントに一ヶ月運用させた結果を公開します。"},
            {"text": "本の教えを、AIで実行可能にする。そんな検証を毎週やっています。",
             "tts": "本の教えを、エーアイで実行可能にする。そんな検証を毎週やっています。"},
            {"text": "続きが気になる方は、チャンネル登録をお願いします。"},
            {"text": "それでは、また次の動画でお会いしましょう。"},
        ],
    },
]


def font(path, size):
    return ImageFont.truetype(path, size)


def wrap_text(draw, text, fnt, max_w):
    """日本語向けの単純な文字単位折り返し."""
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=fnt) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def render_slide(slide):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 左のアクセントバーとパネル
    d.rectangle([0, 0, 14, H], fill=ACCENT)
    d.rectangle([40, 150, W - 40, H - 150], fill=BG_PANEL)
    # kicker / chip / 透かし
    d.text((60, 50), slide["kicker"], font=font(FONT_BOLD, 30), fill=ACCENT)
    chip = slide.get("chip", "")
    if chip:
        f = font(FONT_BOLD, 26)
        tw = d.textlength(chip, font=f)
        d.rounded_rectangle([W - 60 - tw - 36, 44, W - 60, 96], radius=12, outline=ACCENT, width=3)
        d.text((W - 60 - tw - 18, 54), chip, font=f, fill=ACCENT)
    d.text((W - 60, 106), f"{CHANNEL} | {WATERMARK}", font=font(FONT_REG, 20), fill=SUBTEXT, anchor="ra")
    # タイトル(改行対応)
    y = 190
    for tl in slide["title"].split("\n"):
        d.text((90, y), tl, font=font(FONT_BOLD, 58), fill=TEXT)
        y += 78
    # 箇条書き
    y += 24
    for b in slide.get("bullets", []):
        d.ellipse([96, y + 16, 116, y + 36], fill=ACCENT)
        d.text((140, y), b, font=font(FONT_REG, 36), fill=TEXT)
        y += 62
    # フッター
    d.text((60, H - 50), CHANNEL, font=font(FONT_BOLD, 26), fill=SUBTEXT)
    return img


def add_subtitle(base, text):
    img = base.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    f = font(FONT_BOLD, 34)
    lines = wrap_text(d, text, f, W - 240)[:2]
    band_h = 44 * len(lines) + 36
    d.rectangle([0, H - band_h, W, H], fill=(0, 0, 0, 185))
    y = H - band_h + 16
    for ln in lines:
        d.text((W // 2, y), ln, font=f, fill=(255, 255, 255, 255), anchor="ma")
        y += 44
    return Image.alpha_composite(img, overlay).convert("RGB")


def tts(text, out_wav):
    txt = out_wav.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    subprocess.run(
        ["open_jtalk", "-x", DIC, "-m", VOICE, "-r", "1.05", "-s", "48000",
         "-ow", str(out_wav), str(txt)],
        check=True, capture_output=True,
    )
    with wave.open(str(out_wav)) as w:
        return w.getnframes() / w.getframerate()


def render_thumbnail(out_path):
    img = Image.new("RGB", (W, H), (16, 20, 32))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, H], outline=ACCENT, width=10)
    d.text((70, 60), "エッセンシャル思考 × AI検証", font=font(FONT_BOLD, 44), fill=ACCENT)
    d.text((70, 150), "本の教えを", font=font(FONT_BOLD, 84), fill=TEXT)
    d.text((70, 260), "AIに1週間", font=font(FONT_BOLD, 110), fill=ACCENT)
    d.text((70, 400), "任せた結果…", font=font(FONT_BOLD, 84), fill=TEXT)
    d.rounded_rectangle([70, 540, 760, 640], radius=18, fill=ACCENT)
    d.text((100, 558), "会議 -4本 / 退社 -50分", font=font(FONT_BOLD, 52), fill=(16, 20, 32))
    d.text((W - 50, H - 70), CHANNEL + " #01", font=font(FONT_BOLD, 34), fill=SUBTEXT, anchor="ra")
    img.save(out_path)


def main(out_dir):
    out = Path(out_dir)
    frames_dir = out / "frames"
    audio_dir = out / "audio"
    frames_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    concat_lines = []
    wav_parts = []  # (path, trailing_pause_sec)
    idx = 0
    total = 0.0
    for si, scene in enumerate(SCENES):
        base = render_slide(scene["slide"])
        for li, line in enumerate(scene["lines"]):
            wav = audio_dir / f"line_{idx:03d}.wav"
            dur = tts(line.get("tts", line["text"]), wav)
            png = frames_dir / f"line_{idx:03d}.png"
            add_subtitle(base, line["text"]).save(png)
            pause = SCENE_PAUSE if li == len(scene["lines"]) - 1 else LINE_PAUSE
            wav_parts.append((wav, pause))
            concat_lines.append(f"file '{png}'\nduration {dur + pause:.3f}")
            total += dur + pause
            idx += 1
        print(f"scene {si + 1}/{len(SCENES)} done (elapsed video: {total/60:.1f} min)")

    # 音声を1本に結合(行間に無音を挿入)
    narration = out / "narration.wav"
    with wave.open(str(wav_parts[0][0])) as w0:
        params = w0.getparams()
    with wave.open(str(narration), "wb") as wout:
        wout.setparams(params)
        for wav, pause in wav_parts:
            with wave.open(str(wav)) as win:
                wout.writeframes(win.readframes(win.getnframes()))
            wout.writeframes(b"\x00" * int(pause * params.framerate) * params.sampwidth)

    concat_file = out / "frames.txt"
    last_png = frames_dir / f"line_{idx - 1:03d}.png"
    concat_file.write_text("\n".join(concat_lines) + f"\nfile '{last_png}'\n", encoding="utf-8")

    mp4 = out / "sample_video.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-i", str(narration), "-c:v", "libx264", "-preset", "medium", "-crf", "26",
         "-r", "10", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
         "-shortest", str(mp4)],
        check=True, capture_output=True,
    )
    render_thumbnail(out / "thumbnail.png")
    print(f"total length: {total/60:.2f} min -> {mp4}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "build")
