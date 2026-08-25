#!/usr/bin/env python3
"""チャンネルのアイコンとバナーを生成する.

動画と同じキャラ・配色を使うので、見た目が揃う。

    python3 make_branding.py [出力先]        # 既定は ./branding

出力:
    icon.png    800x800   YouTubeは円形に切り抜くので、中央に情報を寄せてある
    banner.png  2048x1152 中央 1235x338 が全デバイスで見える安全領域
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

import build_video as B

# ここを書き換えれば名前を差し替えて作り直せる
NAME = "本のデータ研究所"
TAGLINE = "本を1冊ずつ数えて、読む前にわかることを増やす"
SCHEDULE = "毎週金曜 19時 更新"


def make_icon(path):
    """円形に切り抜かれる前提で、キャラ2人を大きく配置する."""
    S = 800
    # まず円の内側だけを描いてから、円形マスクで抜く(切り出しの境界線を出さない)
    inner = Image.new("RGBA", (S, S), B.CREAM + (255,))
    for key, x in (("noa", -60), ("mei", 320)):
        sprite = B.draw_character(key, 0.0, False, False).resize((540, 540), Image.LANCZOS)
        inner.paste(sprite, (x, 190), sprite)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse([34, 34, S - 34, S - 34], fill=255)

    img = Image.new("RGB", (S, S), B.YELLOW)
    img.paste(inner.convert("RGB"), (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.ellipse([34, 34, S - 34, S - 34], outline=B.INK, width=16)
    # 「数える」チャンネルであることの記号(上部の空きに小さく)
    for i, (w, col) in enumerate([(168, B.PINK), (120, B.SKY), (74, B.PURPLE)]):
        y = 120 + i * 40
        d.rounded_rectangle([316, y, 316 + w, y + 26], radius=13,
                            fill=col, outline=B.INK, width=5)
    img.save(path)


def make_banner(path):
    W, H = 2048, 1152
    img = Image.new("RGB", (W, H), B.CREAM)
    d = ImageDraw.Draw(img)
    for y in range(0, H, 56):
        for x in range(0, W, 56):
            d.ellipse([x, y, x + 8, y + 8], fill=(240, 232, 214))
    B.draw_burst(d, W // 2, H // 2, n=34, r0=300, r1=1500, color=(255, 240, 206))

    # 安全領域(全デバイスで見える範囲)に文字を収める
    sx, sy, sw, sh = (W - 1235) // 2, (H - 338) // 2, 1235, 338
    d.rounded_rectangle([sx - 40, sy - 10, sx + sw + 40, sy + sh + 10],
                        radius=40, fill=B.WHITE, outline=B.INK, width=9)
    B.outlined_text(d, (W // 2, sy + 44), NAME, B.font(B.FONT_BOLD, 118),
                    B.INK, B.WHITE, 5, anchor="ma")
    d.text((W // 2, sy + 196), TAGLINE, font=B.font(B.FONT_REG, 40),
           fill=(96, 100, 122), anchor="ma")
    f = B.font(B.FONT_BOLD, 36)
    tw = d.textlength(SCHEDULE, font=f)
    d.rounded_rectangle([W // 2 - tw // 2 - 28, sy + 256, W // 2 + tw // 2 + 28, sy + 316],
                        radius=30, fill=B.PINK, outline=B.INK, width=6)
    d.text((W // 2, sy + 266), SCHEDULE, font=f, fill=B.WHITE, anchor="ma")

    # キャラは安全領域の外側(PC・TVでのみ見える位置)
    for key, x in (("noa", 150), ("mei", W - 610)):
        sprite = B.draw_character(key, 0.0, False, False).resize((460, 460), Image.LANCZOS)
        img.paste(sprite, (x, H - 470), sprite)
    img.save(path)


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "branding")
    out.mkdir(parents=True, exist_ok=True)
    make_icon(out / "icon.png")
    make_banner(out / "banner.png")
    print(f"チャンネル名: {NAME}")
    print(f"出力: {out}/icon.png (800x800) / {out}/banner.png (2048x1152)")


if __name__ == "__main__":
    main()
