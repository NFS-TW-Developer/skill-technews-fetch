#!/usr/bin/env python3
"""Render editorial-style multi-article TechNews collage cards as PNG images."""

from __future__ import annotations

import argparse
import csv
import json
import re
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

CARD_WIDTH = 1920
CARD_HEIGHT = 1080
MARGIN = 32
GAP = 18
HEADER_HEIGHT = 150
FOOTER_HEIGHT = 48
ACCENT = "#F1602B"
BG_TOP = "#0B1017"
BG_BOTTOM = "#F6F1EA"
TEXT_PRIMARY = "#111111"
TEXT_DARK = "#101820"
TEXT_PANEL_BG = "#FFFDF9"
TEXT_MUTED = "#5E5A55"
PANEL_BORDER = "#DDD6CE"
SHADOW = "#000000"
PANEL_FALLBACK_TOP = "#28384A"
PANEL_FALLBACK_BOTTOM = "#121A22"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    )
}
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/kaiu.ttf"),
    Path("C:/Windows/Fonts/mingliu.ttc"),
    Path("C:/Windows/Fonts/msjh.ttc"),
    Path("C:/Windows/Fonts/msjhl.ttc"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render editorial social collage cards from TechNews rows")
    parser.add_argument("--input-file", required=True, help="Input JSON or CSV file with article rows")
    parser.add_argument("--output-dir", default="outputs/news-collage", help="Directory for PNG collage cards")
    parser.add_argument("--font-path", default=None, help="Optional CNS11643-capable font file path (.ttf/.ttc)")
    parser.add_argument(
        "--articles-per-card",
        type=int,
        default=3,
        help="Articles per collage card; supports dedicated 3-article and 4-article editorial layouts",
    )
    parser.add_argument("--limit", type=int, default=None, help="Only use the first N rows")
    parser.add_argument("--card-title", default=None, help="Optional card title, for example 06/01~06/02 要點")
    return parser.parse_args()


def load_rows(input_path: Path) -> list[dict[str, str]]:
    if input_path.suffix.lower() == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise SystemExit(f"JSON input must be a list: {input_path}")
        rows: list[dict[str, str]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            rows.append({str(key): "" if value is None else str(value) for key, value in item.items()})
        return rows
    if input_path.suffix.lower() == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [{str(key): value or "" for key, value in row.items()} for row in reader]
    raise SystemExit(f"Unsupported input file format: {input_path}")


def pick_font_path(font_path_arg: str | None) -> Path:
    if font_path_arg:
        path = Path(font_path_arg)
        if not path.exists():
            raise SystemExit(f"Font file not found: {path}")
        return path
    for candidate in FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit("No suitable Chinese font found. Use --font-path to provide one.")


def load_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path), size=size)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


def draw_vertical_gradient(image: Image.Image, top_hex: str, bottom_hex: str) -> None:
    draw = ImageDraw.Draw(image)
    top_rgb = hex_to_rgb(top_hex)
    bottom_rgb = hex_to_rgb(bottom_hex)
    for y in range(image.height):
        ratio = y / max(1, image.height - 1)
        color = tuple(int(top + (bottom - top) * ratio) for top, bottom in zip(top_rgb, bottom_rgb))
        draw.line((0, y, image.width, y), fill=color)


def fetch_cover_image(image_url: str) -> Image.Image | None:
    if not image_url:
        return None
    try:
        response = requests.get(image_url, headers=DEFAULT_HEADERS, timeout=20)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")
    except (requests.RequestException, OSError):
        return None


def crop_to_fill(image: Image.Image, width: int, height: int) -> Image.Image:
    source_ratio = image.width / image.height
    target_ratio = width / height
    if source_ratio > target_ratio:
        new_height = height
        new_width = int(height * source_ratio)
    else:
        new_width = width
        new_height = int(width / source_ratio)
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    left = max(0, (new_width - width) // 2)
    top = max(0, (new_height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def panel_background(width: int, height: int, image_url: str, darkness: int) -> Image.Image:
    cover = fetch_cover_image(image_url)
    if cover is None:
        fallback = Image.new("RGB", (width, height), hex_to_rgb(PANEL_FALLBACK_TOP))
        draw_vertical_gradient(fallback, PANEL_FALLBACK_TOP, PANEL_FALLBACK_BOTTOM)
        return fallback

    panel = crop_to_fill(cover, width, height)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, darkness))
    return Image.alpha_composite(panel.convert("RGBA"), overlay).convert("RGB")


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def line_height(font: ImageFont.FreeTypeFont) -> int:
    bbox = font.getbbox("測Ag")
    return int(bbox[3] - bbox[1])


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    lines: list[str] = []
    current = ""
    for char in normalized:
        candidate = current + char
        if current and text_width(draw, candidate, font) > max_width:
            lines.append(current.rstrip())
            current = char
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        if len(last) > 1:
            lines[-1] = last[:-1].rstrip() + "…"
    return lines


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        return fallback
    return cleaned.encode("ascii", errors="ignore").decode("ascii").strip("-") or fallback


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str,
    shadow_offset: int = 3,
) -> None:
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=SHADOW)
    draw.text((x, y), text, font=font, fill=fill)


def draw_title_block(
    draw: ImageDraw.ImageDraw,
    title: str,
    x: int,
    y: int,
    width: int,
    font: ImageFont.FreeTypeFont,
    max_lines: int,
    fill: str,
    shadow: bool = True,
) -> int:
    lines = wrap_text(draw, title or "未命名文章", font, width, max_lines)
    current_y = y
    step = line_height(font) + 10
    for line in lines:
        if shadow:
            draw_text_with_shadow(draw, (x, current_y), line, font, fill)
        else:
            draw.text((x, current_y), line, font=font, fill=fill)
        current_y += step
    return current_y


def editorial_frame_three() -> tuple[tuple[int, int, int, int], list[tuple[int, int, int, int]]]:
    canvas_top = HEADER_HEIGHT
    canvas_bottom = CARD_HEIGHT - FOOTER_HEIGHT - MARGIN
    canvas_height = canvas_bottom - canvas_top
    left_width = 1120
    right_width = CARD_WIDTH - (MARGIN * 2) - GAP - left_width
    hero_rect = (MARGIN, canvas_top, MARGIN + left_width, canvas_bottom)
    small_height = int((canvas_height - GAP) / 2)
    right_x = hero_rect[2] + GAP
    top_rect = (right_x, canvas_top, right_x + right_width, canvas_top + small_height)
    bottom_rect = (right_x, canvas_top + small_height + GAP, right_x + right_width, canvas_bottom)
    return hero_rect, [top_rect, bottom_rect]


def editorial_frame_four() -> tuple[tuple[int, int, int, int], list[tuple[int, int, int, int]]]:
    canvas_top = HEADER_HEIGHT
    canvas_bottom = CARD_HEIGHT - FOOTER_HEIGHT - MARGIN
    canvas_height = canvas_bottom - canvas_top
    canvas_width = CARD_WIDTH - (MARGIN * 2)

    hero_height = int(canvas_height * 0.54)
    hero_rect = (MARGIN, canvas_top, MARGIN + canvas_width, canvas_top + hero_height)

    lower_top = hero_rect[3] + GAP
    small_height = canvas_bottom - lower_top
    small_width = int((canvas_width - (GAP * 2)) / 3)

    rects: list[tuple[int, int, int, int]] = []
    for index in range(3):
        x1 = MARGIN + (small_width + GAP) * index
        x2 = x1 + small_width
        if index == 2:
            x2 = MARGIN + canvas_width
        rects.append((x1, lower_top, x2, canvas_bottom))

    return hero_rect, rects


def draw_panel(
    base_image: Image.Image,
    draw: ImageDraw.ImageDraw,
    row: dict[str, str],
    rect: tuple[int, int, int, int],
    font_path: Path,
    is_hero: bool,
) -> None:
    x1, y1, x2, y2 = rect
    width = x2 - x1
    height = y2 - y1
    image_height = int(height * (0.8 if is_hero else 0.74))
    image_rect = (x1, y1, x2, y1 + image_height)
    text_rect = (x1, image_rect[3], x2, y2)

    darkness = 26 if is_hero else 34
    panel = panel_background(width, image_height, row.get("image", "").strip(), darkness)
    base_image.paste(panel, (x1, y1))

    draw.rectangle(text_rect, fill=TEXT_PANEL_BG)
    draw.rectangle((x1, y1, x2, y2), outline=PANEL_BORDER, width=1)

    title_font = load_font(font_path, 38 if is_hero else 24)

    inset = 28 if is_hero else 18

    title_width = width - (inset * 2)
    title_y = text_rect[1] + (18 if is_hero else 14)
    draw_title_block(
        draw,
        row.get("title", "").strip(),
        x1 + inset,
        title_y,
        title_width,
        title_font,
        2 if is_hero else 2,
        TEXT_DARK,
        shadow=False,
    )


def chunk_rows(rows: list[dict[str, str]], size: int) -> list[list[dict[str, str]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def render_collage(
    rows: list[dict[str, str]],
    font_path: Path,
    output_path: Path,
    page_index: int,
    total_pages: int,
    card_title: str | None,
    articles_per_card: int,
) -> None:
    global HEADER_HEIGHT
    original_header_height = HEADER_HEIGHT
    HEADER_HEIGHT = 112 if card_title else 24

    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), hex_to_rgb(BG_BOTTOM))
    draw = ImageDraw.Draw(image)

    header_title_font = load_font(font_path, 40)
    if card_title:
        draw.text((MARGIN, 28), card_title, font=header_title_font, fill=TEXT_DARK)

    if articles_per_card == 4:
        hero_rect, side_rects = editorial_frame_four()
    else:
        hero_rect, side_rects = editorial_frame_three()

    hero_row = rows[0]
    draw_panel(image, draw, hero_row, hero_rect, font_path, is_hero=True)

    for row, rect in zip(rows[1:articles_per_card], side_rects):
        draw_panel(image, draw, row, rect, font_path, is_hero=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    HEADER_HEIGHT = original_header_height


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    if args.articles_per_card <= 0:
        raise SystemExit("--articles-per-card must be greater than 0")

    rows = load_rows(input_path)
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("No article rows available for rendering")

    font_path = pick_font_path(args.font_path)
    output_dir = Path(args.output_dir)
    if args.articles_per_card not in (3, 4):
        raise SystemExit("--articles-per-card currently supports 3 or 4")

    groups = chunk_rows(rows, args.articles_per_card)
    metadata: list[dict[str, object]] = []

    for index, group in enumerate(groups, start=1):
        first_title = group[0].get("title", "").strip() or f"page-{index}"
        output_path = output_dir / f"{index:02d}-{slugify(first_title, f'page-{index}')}.png"
        render_collage(group, font_path, output_path, index, len(groups), args.card_title, args.articles_per_card)
        metadata.append(
            {
                "page": index,
                "image": str(output_path),
                "card_title": args.card_title or "",
                "articles": [
                    {
                        "title": row.get("title", "").strip(),
                        "link": row.get("link", "").strip(),
                        "image": row.get("image", "").strip(),
                        "date": row.get("date", "").strip(),
                    }
                    for row in group
                ],
            }
        )
        print(f"Rendered collage {index}: {output_path}")

    metadata_path = output_dir / "news_collage_cards.json"
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved metadata to {metadata_path}")
    print(f"Font used: {font_path}")


if __name__ == "__main__":
    main()
