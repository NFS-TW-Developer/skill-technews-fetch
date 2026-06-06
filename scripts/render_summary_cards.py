#!/usr/bin/env python3
"""Render summary cards for selected TechNews articles as PNG images."""

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

CARD_WIDTH = 1200
CARD_HEIGHT = 1600
PADDING_X = 88
PADDING_Y = 82
HERO_HEIGHT = 620
ACCENT_COLOR = "#D24A2F"
BACKGROUND_TOP = "#F6E7D8"
BACKGROUND_BOTTOM = "#FFF9F1"
TITLE_COLOR = "#17120F"
BODY_COLOR = "#3D312A"
MUTED_COLOR = "#7A6659"
DIVIDER_COLOR = "#DFC9B5"
QUOTE_COLOR = "#F3E4D4"
SOURCE_BADGE_BG = "#17120F"
SOURCE_BADGE_TEXT = "#FFF8F0"
OVERLAY_TOP = "#111111"
OVERLAY_BOTTOM = "#000000"
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
    parser = argparse.ArgumentParser(description="Render summary cards for TechNews article rows")
    parser.add_argument("--input-file", required=True, help="Input JSON or CSV file with article rows")
    parser.add_argument(
        "--output-dir",
        default="outputs/cards",
        help="Directory for rendered PNG cards and summary metadata",
    )
    parser.add_argument(
        "--font-path",
        default=None,
        help="Optional CNS11643-capable font file path (.ttf/.ttc)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Render only the first N rows after loading",
    )
    parser.add_argument(
        "--max-bullets",
        type=int,
        default=3,
        help="Maximum number of summary bullets per article",
    )
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


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip())
    cleaned = cleaned.strip("-")
    if not cleaned:
        return fallback
    return cleaned.encode("ascii", errors="ignore").decode("ascii").strip("-") or fallback


def sentence_chunks(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?])\s*|(?<=\.)\s+(?=[A-Z0-9])", normalized)
    return [part.strip(" \n\r\t-•") for part in parts if part.strip(" \n\r\t-•")]


def truncate_text(text: str, limit: int) -> str:
    stripped = re.sub(r"\s+", " ", text).strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: max(0, limit - 1)].rstrip() + "…"


def summarize_article(row: dict[str, str], max_bullets: int) -> dict[str, object]:
    title = row.get("title", "").strip() or "未命名文章"
    content = row.get("content", "").strip()
    pieces = sentence_chunks(content)
    if not pieces:
        fallback_body = row.get("author", "").strip() or row.get("link", "").strip() or "目前沒有可用正文。"
        pieces = [fallback_body]

    bullets: list[str] = []
    for piece in pieces:
        compact = truncate_text(piece, 72)
        if compact and compact not in bullets:
            bullets.append(compact)
        if len(bullets) >= max(1, max_bullets):
            break

    quote = bullets[0]
    caption_source = content or title
    caption = truncate_text(caption_source, 110)
    return {
        "title": title,
        "date": row.get("date", "").strip(),
        "author": row.get("author", "").strip(),
        "category": row.get("category", "").strip(),
        "link": row.get("link", "").strip(),
        "image": row.get("image", "").strip(),
        "summary_bullets": bullets,
        "summary_quote": quote,
        "card_caption": caption,
    }


def draw_vertical_gradient(image: Image.Image, top_hex: str, bottom_hex: str) -> None:
    draw = ImageDraw.Draw(image)
    top_rgb = tuple(int(top_hex[index : index + 2], 16) for index in (1, 3, 5))
    bottom_rgb = tuple(int(bottom_hex[index : index + 2], 16) for index in (1, 3, 5))
    for y in range(image.height):
        ratio = y / max(1, image.height - 1)
        color = tuple(int(top + (bottom - top) * ratio) for top, bottom in zip(top_rgb, bottom_rgb))
        draw.line((0, y, image.width, y), fill=color)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    return (
        int(value[1:3], 16),
        int(value[3:5], 16),
        int(value[5:7], 16),
    )


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


def hero_image_with_overlay(cover_image: Image.Image | None) -> Image.Image:
    if cover_image is None:
        fallback = Image.new("RGB", (CARD_WIDTH, HERO_HEIGHT), hex_to_rgb(BACKGROUND_TOP))
        draw_vertical_gradient(fallback, "#8F3928", "#221814")
        return fallback

    hero = crop_to_fill(cover_image, CARD_WIDTH, HERO_HEIGHT)
    overlay = Image.new("RGBA", (CARD_WIDTH, HERO_HEIGHT), (0, 0, 0, 0))
    top_rgb = hex_to_rgb(OVERLAY_TOP)
    bottom_rgb = hex_to_rgb(OVERLAY_BOTTOM)
    overlay_pixels = overlay.load()
    if overlay_pixels is None:
        return hero
    for y in range(HERO_HEIGHT):
        ratio = y / max(1, HERO_HEIGHT - 1)
        alpha = int(40 + (190 * ratio))
        color = tuple(int(top + (bottom - top) * ratio) for top, bottom in zip(top_rgb, bottom_rgb))
        for x in range(CARD_WIDTH):
            overlay_pixels[x, y] = (color[0], color[1], color[2], alpha)
    return Image.alpha_composite(hero.convert("RGBA"), overlay).convert("RGB")


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(right - left)


def line_height(font: ImageFont.FreeTypeFont) -> int:
    bbox = font.getbbox("測Ag")
    return int(bbox[3] - bbox[1])


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    max_lines: int | None = None,
) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    if not normalized.strip():
        return []

    lines: list[str] = []
    for paragraph in normalized.split("\n"):
        stripped = paragraph.strip()
        if not stripped:
            continue

        current = ""
        for char in stripped:
            candidate = current + char
            if current and text_width(draw, candidate, font) > max_width:
                lines.append(current.rstrip())
                current = char
            else:
                current = candidate

        if current.strip():
            lines.append(current.rstrip())

    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = truncate_text(lines[-1], max(8, len(lines[-1]) - 1))
    return lines


def draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: str,
    spacing: int,
) -> int:
    current_y = y
    step = line_height(font) + spacing
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += step
    return current_y


def render_card(summary: dict[str, object], font_path: Path, output_path: Path) -> None:
    image = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), "white")
    draw_vertical_gradient(image, BACKGROUND_TOP, BACKGROUND_BOTTOM)
    cover_image = fetch_cover_image(str(summary.get("image", "")))
    image.paste(hero_image_with_overlay(cover_image), (0, 0))
    draw = ImageDraw.Draw(image)

    title_font = load_font(font_path, 52)
    meta_font = load_font(font_path, 24)
    badge_font = load_font(font_path, 22)
    bullet_font = load_font(font_path, 34)
    quote_font = load_font(font_path, 28)
    caption_font = load_font(font_path, 26)
    hero_meta_font = load_font(font_path, 26)

    draw.rounded_rectangle((58, 54, CARD_WIDTH - 58, CARD_HEIGHT - 54), radius=42, outline=DIVIDER_COLOR, width=3)
    draw.rounded_rectangle((PADDING_X, 68, PADDING_X + 164, 118), radius=18, fill=SOURCE_BADGE_BG)
    draw.text((PADDING_X + 24, 80), "TECHNEWS", font=badge_font, fill=SOURCE_BADGE_TEXT)

    category = str(summary.get("category", "")).strip()
    date = str(summary.get("date", "")).strip()
    author = str(summary.get("author", "")).strip()
    meta_parts = [part for part in (category, date, author) if part]
    meta_text = "  |  ".join(meta_parts) or "TechNews article"

    title_lines = wrap_text(draw, str(summary["title"]), title_font, CARD_WIDTH - (PADDING_X * 2), max_lines=4)
    hero_title_y = HERO_HEIGHT - 220
    draw_lines(draw, title_lines, PADDING_X, hero_title_y, title_font, "#FFF9F2", 10)
    draw.text((PADDING_X, HERO_HEIGHT - 60), meta_text, font=hero_meta_font, fill="#F7E7D7")

    content_top = HERO_HEIGHT + 34
    draw.rounded_rectangle(
        (48, HERO_HEIGHT - 34, CARD_WIDTH - 48, CARD_HEIGHT - 48),
        radius=40,
        fill="#FFF9F1",
        outline=DIVIDER_COLOR,
        width=3,
    )
    y = content_top

    draw.line((PADDING_X, y, CARD_WIDTH - PADDING_X, y), fill=DIVIDER_COLOR, width=3)
    y += 36

    quote_top = y
    quote_height = 210
    draw.rounded_rectangle(
        (PADDING_X, quote_top, CARD_WIDTH - PADDING_X, quote_top + quote_height),
        radius=28,
        fill=QUOTE_COLOR,
    )
    draw.text((PADDING_X + 34, quote_top + 28), "摘要焦點", font=badge_font, fill=ACCENT_COLOR)
    quote_lines = wrap_text(
        draw,
        str(summary["summary_quote"]),
        quote_font,
        CARD_WIDTH - (PADDING_X * 2) - 68,
        max_lines=4,
    )
    draw_lines(draw, quote_lines, PADDING_X + 34, quote_top + 76, quote_font, BODY_COLOR, 8)
    y = quote_top + quote_height + 40

    draw.text((PADDING_X, y), "三點整理", font=badge_font, fill=ACCENT_COLOR)
    y += line_height(badge_font) + 24

    bullets_value = summary.get("summary_bullets", [])
    bullets = bullets_value if isinstance(bullets_value, list) else []
    for bullet in bullets:
        bullet_text = str(bullet)
        bullet_lines = wrap_text(draw, bullet_text, bullet_font, CARD_WIDTH - (PADDING_X * 2) - 46, max_lines=3)
        draw.text((PADDING_X, y), "•", font=bullet_font, fill=ACCENT_COLOR)
        y = draw_lines(draw, bullet_lines, PADDING_X + 38, y + 2, bullet_font, BODY_COLOR, 8)
        y += 18

    footer_top = CARD_HEIGHT - 250
    draw.line((PADDING_X, footer_top, CARD_WIDTH - PADDING_X, footer_top), fill=DIVIDER_COLOR, width=3)
    draw.text((PADDING_X, footer_top + 28), "卡片說明", font=badge_font, fill=ACCENT_COLOR)
    caption_lines = wrap_text(
        draw,
        str(summary["card_caption"]),
        caption_font,
        CARD_WIDTH - (PADDING_X * 2),
        max_lines=4,
    )
    draw_lines(draw, caption_lines, PADDING_X, footer_top + 72, caption_font, BODY_COLOR, 7)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    rows = load_rows(input_path)
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit("No article rows available for rendering")

    output_dir = Path(args.output_dir)
    font_path = pick_font_path(args.font_path)
    summaries: list[dict[str, object]] = []

    for index, row in enumerate(rows, start=1):
        summary = summarize_article(row, args.max_bullets)
        slug = slugify(str(summary["title"]), f"article-{index}")
        image_path = output_dir / f"{index:02d}-{slug}.png"
        render_card(summary, font_path, image_path)
        summary["card_image"] = str(image_path)
        summaries.append(summary)
        print(f"Rendered card {index}: {image_path}")

    metadata_path = output_dir / "summary_cards.json"
    metadata_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved metadata to {metadata_path}")
    print(f"Font used: {font_path}")


if __name__ == "__main__":
    main()
