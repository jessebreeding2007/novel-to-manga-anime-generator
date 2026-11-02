#!/usr/bin/env python3
"""Stitch generated panels into a vertical webtoon strip, with optional auto-lettering.

Usage:
  python stitch.py comic_plan.json                 # output/webtoon.png + output/webtoon_slices/
  python stitch.py comic_plan.json --no-letter     # clean art, letter it yourself
  python stitch.py comic_plan.json --width 800 --slice-height 1280 --font /path/font.ttf

Dialogue is placed in the white space above each panel (never over the art):
speech = rounded balloon, thought = dashed balloon, narration = box, sfx = bold text.
Balloons sit left / right / center following each line's "side".
"""

import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

GAPS = {"short": 40, "medium": 120, "long": 320}
BG = (255, 255, 255)
INK = (20, 20, 20)
CAPTION_BG = (250, 244, 214)

FONT_CANDIDATES = {
    "cjk": [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
    ],
    "latin": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ],
}


def find_font(lang, explicit=None):
    if explicit:
        return explicit
    order = ["cjk", "latin"] if lang in ("zh", "ja") else ["latin", "cjk"]
    for group in order:
        for path in FONT_CANDIDATES[group]:
            if os.path.exists(path):
                return path
    return None


def load_font(path, size):
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def wrap(draw, text, font, max_width):
    """Wrap by words when the text has spaces, otherwise by characters (CJK)."""
    units = text.split(" ") if " " in text.strip() else list(text)
    sep = " " if " " in text.strip() else ""
    lines, cur = [], ""
    for u in units:
        trial = f"{cur}{sep}{u}" if cur else u
        if draw.textlength(trial, font=font) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = u
    if cur:
        lines.append(cur)
    return lines


def _dashed_round_rect(draw, box, radius, width):
    """Thought balloon: rounded outline broken into dashes on the straight edges."""
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=radius, fill=BG, outline=INK, width=width)
    for x in range(int(x0 + radius) + 6, int(x1 - radius) - 6, 18):
        for y in (y0, y1):
            draw.line([(x, y), (x + 7, y)], fill=BG, width=width + 2)


def render_lines(lines, width, font_path, scale=1.0):
    """Render a panel's lettering block. Returns an RGB image (or None if no lines)."""
    if not lines:
        return None
    size = max(14, int(26 * scale))
    font = load_font(font_path, size)
    sfx_font = load_font(font_path, int(size * 1.6))
    pad, margin, gap = int(18 * scale), int(28 * scale), int(14 * scale)
    max_w = int(width * 0.62)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    blocks = []
    for ln in lines:
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        kind = ln.get("kind", "speech")
        f = sfx_font if kind == "sfx" else font
        wrapped = wrap(probe, text, f, max_w - 2 * pad if kind != "narration" else width - 2 * margin - 2 * pad)
        line_h = int(f.size * 1.3)
        tw = max(int(probe.textlength(w, font=f)) for w in wrapped)
        bw, bh = tw + 2 * pad, line_h * len(wrapped) + 2 * pad
        if kind == "narration":
            bw = width - 2 * margin
        blocks.append((kind, ln.get("side", "center"), wrapped, f, line_h, bw, bh))
    if not blocks:
        return None

    total_h = sum(b[6] for b in blocks) + gap * (len(blocks) + 1)
    img = Image.new("RGB", (width, total_h), BG)
    draw = ImageDraw.Draw(img)
    y = gap
    stroke = max(2, int(3 * scale))
    for kind, side, wrapped, f, line_h, bw, bh in blocks:
        if side == "left":
            x = margin
        elif side == "right":
            x = width - margin - bw
        else:
            x = (width - bw) // 2
        box = (x, y, x + bw, y + bh)
        if kind == "narration":
            draw.rectangle(box, fill=CAPTION_BG, outline=INK, width=stroke)
        elif kind == "thought":
            _dashed_round_rect(draw, box, radius=min(bh // 2, 48), width=stroke)
        elif kind == "speech":
            draw.rounded_rectangle(box, radius=min(bh // 2, 48), fill=BG, outline=INK, width=stroke)
            # small tail pointing down toward the panel, on the speaker's side
            tx = x + bw // 4 if side == "left" else x + 3 * bw // 4 if side == "right" else x + bw // 2
            tail = [(tx - 12, y + bh - stroke), (tx + 12, y + bh - stroke), (tx, y + bh + gap // 2 + 4)]
            draw.polygon(tail, fill=BG, outline=None)
            draw.line([tail[0], tail[2], tail[1]], fill=INK, width=stroke)
        ty = y + pad
        for w in wrapped:
            if kind == "narration":
                tx0 = x + pad
            else:
                tx0 = x + (bw - int(draw.textlength(w, font=f))) // 2
            if kind == "sfx":
                draw.text((tx0, ty), w, font=f, fill=INK, stroke_width=stroke, stroke_fill=BG)
            else:
                draw.text((tx0, ty), w, font=f, fill=INK)
            ty += line_h
        y += bh + gap
    return img


def build_strip(plan, panels_dir, width=800, letter=True, font_path=None, log=print):
    """Return (strip_image, missing_panel_ids)."""
    scale = width / 800
    pieces, missing = [Image.new("RGB", (width, int(GAPS["medium"] * scale)), BG)], []
    for p in plan["panels"]:
        path = os.path.join(panels_dir, f"{p['id']}.png")
        if letter:
            block = render_lines(p.get("lines", []), width, font_path, scale)
            if block:
                pieces.append(block)
        if not os.path.exists(path):
            missing.append(p["id"])
            continue
        with Image.open(path) as im:
            im = im.convert("RGB")
            h = round(im.height * width / im.width)
            pieces.append(im.resize((width, h), Image.LANCZOS))
        pieces.append(Image.new("RGB", (width, int(GAPS.get(p.get("gap_after"), 120) * scale)), BG))
    if missing:
        log(f"[stitch] skipped {len(missing)} missing panel(s): {' '.join(missing)}")
    strip = Image.new("RGB", (width, sum(x.height for x in pieces)), BG)
    y = 0
    for x in pieces:
        strip.paste(x, (0, y))
        y += x.height
    return strip, missing


def slice_strip(strip, slice_height):
    return [strip.crop((0, top, strip.width, min(top + slice_height, strip.height)))
            for top in range(0, strip.height, slice_height)]


def stitch(plan_path, out=None, width=800, slice_height=1280, letter=True, font=None, log=print):
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    out = out or os.path.join(os.path.dirname(os.path.abspath(plan_path)), "output")
    font_path = find_font(plan.get("lang"), font)
    if letter and not font_path:
        log("[stitch] no TrueType font found; using Pillow's default (Latin only). Pass --font.")
    strip, missing = build_strip(plan, os.path.join(out, "panels"), width, letter, font_path, log)
    full = os.path.join(out, "webtoon.png")
    strip.save(full, optimize=True)
    slices_dir = os.path.join(out, "webtoon_slices")
    os.makedirs(slices_dir, exist_ok=True)
    for old in os.listdir(slices_dir):
        if old.endswith(".jpg"):
            os.remove(os.path.join(slices_dir, old))
    parts = slice_strip(strip, slice_height) if slice_height else []
    for i, part in enumerate(parts, 1):
        part.save(os.path.join(slices_dir, f"{i:03d}.jpg"), quality=90)
    log(f"[stitch] {full} ({strip.width}x{strip.height}), {len(parts)} slices in {slices_dir}")
    return full, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out", default=None, help="output folder used by run_comic.py")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--slice-height", type=int, default=1280, help="0 = no slices")
    ap.add_argument("--no-letter", action="store_true", help="don't draw dialogue")
    ap.add_argument("--font", default=None, help="TrueType/OpenType font for lettering")
    args = ap.parse_args()
    _, missing = stitch(args.plan, args.out, args.width, args.slice_height,
                        not args.no_letter, args.font)
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
