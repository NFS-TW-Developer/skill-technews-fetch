#!/usr/bin/env python3
"""Prototype scraper for TechNews category pages."""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import random
import sys
import time
from datetime import datetime
from datetime import date
from datetime import timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://technews.tw/category"
HTML_PARSER = "html.parser"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    )
}
SEMICONDUCTOR_CATEGORIES = {
    "semiconductor": {"label": "半導體", "parent": None},
    "semiconductor/chip": {"label": "晶片", "parent": "semiconductor"},
    "semiconductor/chip/cpu": {"label": "處理器", "parent": "semiconductor/chip"},
    "semiconductor/chip/gpu": {"label": "GPU", "parent": "semiconductor/chip"},
    "semiconductor/chip/memory": {"label": "記憶體", "parent": "semiconductor/chip"},
    "semiconductor/ic-設計": {"label": "IC 設計", "parent": "semiconductor"},
    "semiconductor/封裝測試": {"label": "封裝測試", "parent": "semiconductor"},
    "semiconductor/晶圓": {"label": "晶圓", "parent": "semiconductor"},
}

COMPONENT_CATEGORIES = {
    "ccc": {"label": "3C", "parent": None},
    "ccc/accessory": {"label": "3C周邊", "parent": "ccc"},
    "component": {"label": "零組件", "parent": None},
    "component/dian-chi": {"label": "電池", "parent": "component"},
    "component/display-c": {"label": "面板", "parent": "component"},
    "component/光電科技": {"label": "光電科技", "parent": "component"},
}

FINANCE_CATEGORIES = {
    "finance": {"label": "財經", "parent": None},
    "finance/financial_statement": {"label": "財報", "parent": "finance"},
    "finance/finance-report": {"label": "財報快訊", "parent": "finance"},
    "finance/realestate": {"label": "房地產", "parent": "finance"},
    "finance/證券": {"label": "證券", "parent": "finance"},
    "finance/金融政策": {"label": "金融政策", "parent": "finance"},
    "fintech": {"label": "Fintech", "parent": "finance"},
    "fintech/cryptocurrency": {"label": "加密貨幣", "parent": "fintech"},
    "payment": {"label": "支付方案", "parent": "finance"},
    "國際貿易": {"label": "國際貿易", "parent": "finance"},
    "國際貿易/國際金融": {"label": "國際金融", "parent": "國際貿易"},
}

INTERNET_CATEGORIES = {
    "amazon": {"label": "Amazon", "parent": "internet"},
    "entertainment": {"label": "電子娛樂", "parent": "internet"},
    "fb": {"label": "Facebook", "parent": "internet"},
    "google": {"label": "Google", "parent": "internet"},
    "internet": {"label": "網路", "parent": None},
    "internet/開放資料": {"label": "開放資料", "parent": "internet"},
    "internet/電子商務": {"label": "電子商務", "parent": "internet"},
    "internet/雲端": {"label": "雲端", "parent": "internet"},
    "internet-of-things-internet": {"label": "物聯網", "parent": "internet"},
}

CUTTING_EDGE_CATEGORIES = {
    "ai": {"label": "AI", "parent": "cutting-edge"},
    "cutting-edge": {"label": "尖端科技", "parent": None},
    "cutting-edge/drone": {"label": "無人機", "parent": "cutting-edge"},
    "cutting-edge/leos": {"label": "低軌衛星", "parent": "cutting-edge"},
    "cutting-edge/奈米": {"label": "奈米", "parent": "cutting-edge"},
    "cutting-edge/材料": {"label": "材料", "parent": "cutting-edge"},
    "cutting-edge/機器人": {"label": "機器人", "parent": "cutting-edge"},
    "cutting-edge/航太科技": {"label": "航太科技", "parent": "cutting-edge"},
    "軍事科技": {"label": "軍事科技", "parent": None},
    "transport/car-tech": {"label": "汽車科技", "parent": None},
}

SCIENCE_AND_LIFE_CATEGORIES = {
    "biotech": {"label": "生物科技", "parent": None},
    "biotech/醫療": {"label": "醫療科技", "parent": "biotech"},
    "mobiledevice": {"label": "行動裝置", "parent": None},
    "natural-science": {"label": "自然科學", "parent": None},
    "natural-science/環境科學": {"label": "環境科學", "parent": "natural-science"},
    "tech-life": {"label": "科技生活", "parent": None},
    "科技教育": {"label": "科技教育", "parent": None},
}

ENERGY_CATEGORIES = {
    "能源科技": {"label": "能源科技", "parent": None},
    "能源科技/nuclear": {"label": "核能", "parent": "能源科技"},
    "能源科技/solar-energy": {"label": "太陽能", "parent": "能源科技"},
    "能源科技/wind-power": {"label": "風力", "parent": "能源科技"},
    "能源科技/電力儲存": {"label": "電力儲存", "parent": "能源科技"},
}

CATEGORY_REGISTRY = {
    **SEMICONDUCTOR_CATEGORIES,
    **COMPONENT_CATEGORIES,
    **FINANCE_CATEGORIES,
    **INTERNET_CATEGORIES,
    **CUTTING_EDGE_CATEGORIES,
    **SCIENCE_AND_LIFE_CATEGORIES,
    **ENERGY_CATEGORIES,
}

stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
if callable(stdout_reconfigure):
    stdout_reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch TechNews category articles")
    parser.add_argument(
        "--category",
        default=None,
        help="Category slug or subcategory path, e.g. ai or semiconductor/chip/cpu",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help="Topic keyword used to auto-guess the most suitable category",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List supported category slugs and exit",
    )
    parser.add_argument(
        "--show-category-candidates",
        action="store_true",
        help="Show the best matching categories for --topic and exit",
    )
    parser.add_argument("--start-page", type=int, default=1, help="Start page number")
    parser.add_argument("--end-page", type=int, default=3, help="End page number")
    parser.add_argument(
        "--period",
        choices=("today", "last-7-days", "last-30-days"),
        default=None,
        help="Relative date range shortcut",
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Only keep articles on or after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Only keep articles on or before this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Fetch full article content from each article page",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a short digest after scraping",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path; defaults to outputs/<category>-<timestamp>.<ext>",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.5,
        help="Minimum delay between requests in seconds",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=1.5,
        help="Maximum delay between requests in seconds",
    )
    return parser.parse_args()


def validate_category(category: str) -> str:
    normalized = category.strip().strip("/").lower()
    if normalized not in CATEGORY_REGISTRY:
        supported = ", ".join(sorted(CATEGORY_REGISTRY))
        raise SystemExit(f"Unsupported category: {category}. Supported: {supported}")
    return normalized


def normalize_topic(topic: str) -> str:
    return topic.strip().strip("/").lower()


def rank_categories_for_topic(topic: str) -> list[tuple[str, int]]:
    normalized = normalize_topic(topic)
    ranked: list[tuple[str, int]] = []

    for slug, category in CATEGORY_REGISTRY.items():
        label = str(category["label"]).lower()
        slug_tail = slug.split("/")[-1]
        slug_parts = slug.lower().split("/")
        score = 0
        label_ratio = difflib.SequenceMatcher(None, normalized, label).ratio()
        slug_ratio = difflib.SequenceMatcher(None, normalized, slug_tail).ratio()

        if normalized == slug:
            score = 100
        elif normalized == label:
            score = 95
        elif normalized in slug:
            score = 80
        elif normalized in label:
            score = 75
        elif slug_tail in normalized:
            score = 60
        elif label in normalized:
            score = 55
        elif normalized in slug_parts:
            score = 50
        else:
            score = max(int(label_ratio * 100) - 20, int(slug_ratio * 100) - 25, 0)

        if score > 0:
            ranked.append((slug, score))

    ranked.sort(key=lambda item: (-item[1], item[0]))
    return ranked


def guess_category_from_topic(topic: str) -> str:
    ranked = rank_categories_for_topic(topic)
    if ranked:
        return ranked[0][0]

    raise SystemExit(
        f"No category guess available for topic: {topic}. Use --list-categories or --category directly."
    )


def print_topic_candidates(topic: str, limit: int = 5) -> None:
    ranked = rank_categories_for_topic(topic)
    print(f"Topic: {topic}")
    if not ranked:
        print("No matching categories. Use --list-categories to inspect supported categories.")
        return
    print("Top category candidates:")
    for slug, score in ranked[:limit]:
        print(f"- {slug} ({category_label(slug)}) score={score}")


def print_supported_categories() -> None:
    root_categories = sorted(
        slug for slug, category in CATEGORY_REGISTRY.items() if category.get("parent") is None
    )
    for slug in root_categories:
        print_category_branch(slug)


def print_category_branch(slug: str, depth: int = 0) -> None:
    category = CATEGORY_REGISTRY[slug]
    indent = "  " * depth
    print(f"{indent}{slug}\t{category['label']}")
    children = sorted(
        child_slug
        for child_slug, child_category in CATEGORY_REGISTRY.items()
        if child_category.get("parent") == slug
    )
    for child_slug in children:
        print_category_branch(child_slug, depth + 1)


def category_label(category: str) -> str:
    return str(CATEGORY_REGISTRY[category]["label"])


def category_path_to_filename(category: str) -> str:
    return category.replace("/", "-")


def date_range_suffix(start_date: date | None, end_date: date | None) -> str:
    if start_date is None and end_date is None:
        return ""
    start_text = start_date.isoformat() if start_date is not None else "open"
    end_text = end_date.isoformat() if end_date is not None else "open"
    return f"-{start_text}_to_{end_text}"


def parse_date_boundary(value: str | None, label: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"{label} format error, use YYYY-MM-DD: {value}") from exc


def resolve_date_range(
    period: str | None,
    start_date_value: str | None,
    end_date_value: str | None,
) -> tuple[date | None, date | None]:
    start_date = parse_date_boundary(start_date_value, "start_date")
    end_date = parse_date_boundary(end_date_value, "end_date")

    if period is None:
        return start_date, end_date
    if start_date is not None or end_date is not None:
        raise SystemExit("Use either --period or explicit --start-date/--end-date, not both")

    today = date.today()
    if period == "today":
        return today, today
    if period == "last-7-days":
        return today - timedelta(days=6), today
    if period == "last-30-days":
        return today - timedelta(days=29), today
    raise SystemExit(f"Unsupported period: {period}")


def sleep_briefly(min_delay: float, max_delay: float) -> None:
    if max_delay < min_delay:
        min_delay, max_delay = max_delay, min_delay
    time.sleep(random.uniform(min_delay, max_delay))


def format_date(raw_date: str) -> str:
    try:
        parsed = datetime.strptime(raw_date, "%Y 年 %m 月 %d 日 %H:%M")
    except ValueError:
        return raw_date
    return parsed.strftime("%Y-%m-%d %H:%M")


def parse_article_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M").date()
    except ValueError:
        return None


def article_in_range(article_date: date | None, start_date: date | None, end_date: date | None) -> bool:
    if article_date is None:
        return True
    if start_date is not None and article_date < start_date:
        return False
    if end_date is not None and article_date > end_date:
        return False
    return True


def summarize_rows(rows: list[dict[str, str]], category: str, topic: str | None) -> str:
    label = category_label(category)
    title_subject = topic or label
    lines = [f"## TechNews Digest: {title_subject}", ""]
    lines.append(f"- Category: `{category}` ({label})")
    lines.append(f"- Articles: {len(rows)}")
    if not rows:
        lines.append("")
        lines.append("No articles matched the current filters.")
        return "\n".join(lines)

    dates = [row.get("date", "") for row in rows if row.get("date")]
    if dates:
        lines.append(f"- Date span: {dates[-1]} to {dates[0]}")

    lines.append("")
    lines.append("### Headlines")
    for index, row in enumerate(rows[:10], start=1):
        title = row.get("title") or "-"
        article_date = row.get("date") or "-"
        author = row.get("author") or "-"
        lines.append(f"{index}. {title} ({article_date}, {author})")

    return "\n".join(lines)


def fetch_html(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
    response.raise_for_status()
    return BeautifulSoup(response.text, HTML_PARSER)


def extract_article_content(link: str) -> str:
    if not link:
        return ""
    try:
        page = fetch_html(link)
    except requests.RequestException:
        return ""
    paragraphs = [node.get_text(strip=True) for node in page.select("div.indent > p")]
    return "\n".join(text for text in paragraphs if text)


def extract_articles(
    category: str,
    page_number: int,
    min_delay: float,
    max_delay: float,
    start_date: date | None,
    end_date: date | None,
    include_content: bool,
) -> tuple[list[dict[str, str]], bool]:
    category_url = f"{BASE_URL}/{category}/page/{page_number}/"
    page = fetch_html(category_url)
    site_content = page.find("section", {"class": "site-content"})
    if site_content is None:
        return [], False

    items = site_content.find_all("article")
    results: list[dict[str, str]] = []
    saw_older_article = False
    for item in items:
        item_header = item.find("header", {"class": "entry-header"})
        item_entry = item.find("div", {"class": "entry-content"})
        if item_header is None:
            continue

        a_tag = item_header.find("a")
        if a_tag is None:
            continue

        spans = item_header.find_all("span", {"class": "body"})
        author = spans[0].get_text(strip=True) if len(spans) > 0 else ""
        raw_date = spans[1].get_text(strip=True) if len(spans) > 1 else ""

        image = ""
        if item_entry is not None:
            img_tag = item_entry.find("img")
            if img_tag is not None:
                image = img_tag.get("data-src") or img_tag.get("src") or ""

        link = a_tag.get("href", "").strip()
        normalized_date = format_date(raw_date)
        article_date = parse_article_date(normalized_date)
        if article_date is not None and start_date is not None and article_date < start_date:
            saw_older_article = True
        if not article_in_range(article_date, start_date, end_date):
            sleep_briefly(min_delay, max_delay)
            continue

        record = {
            "category": category,
            "postID": item.get("id", ""),
            "title": a_tag.get("title", "").strip(),
            "link": link,
            "image": image,
            "date": normalized_date,
            "author": author,
            "content": extract_article_content(link) if include_content else "",
        }
        results.append(record)
        sleep_briefly(min_delay, max_delay)

    return results, saw_older_article


def default_output_path(
    category: str,
    output_format: str,
    start_date: date | None,
    end_date: date | None,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_category = category_path_to_filename(category)
    suffix = date_range_suffix(start_date, end_date)
    return Path("outputs") / f"technews-{safe_category}{suffix}-{timestamp}.{output_format}"


def write_json(output_path: Path, rows: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(output_path: Path, rows: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["category", "postID", "title", "link", "image", "date", "author", "content"]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    if args.list_categories:
        print_supported_categories()
        return
    if args.show_category_candidates:
        if not args.topic:
            raise SystemExit("Use --topic with --show-category-candidates")
        print_topic_candidates(str(args.topic))
        return

    if not args.category and not args.topic:
        raise SystemExit("Use --category or --topic")

    if args.category:
        category = validate_category(args.category)
    else:
        category = validate_category(guess_category_from_topic(str(args.topic)))
        print_topic_candidates(str(args.topic), limit=3)
        print(f"Guessed category: {category} ({category_label(category)})")

    start_date, end_date = resolve_date_range(args.period, args.start_date, args.end_date)
    if start_date and end_date and start_date > end_date:
        raise SystemExit("start_date must be earlier than or equal to end_date")

    rows: list[dict[str, str]] = []
    if start_date or end_date:
        start_label = start_date.isoformat() if start_date else "open"
        end_label = end_date.isoformat() if end_date else "open"
        print(f"Date filter: {start_label} to {end_label}")
    print(f"Include content: {'yes' if args.include_content else 'no'}")

    for page_number in range(args.start_page, args.end_page + 1):
        try:
            page_rows, saw_older_article = extract_articles(
                category,
                page_number,
                args.min_delay,
                args.max_delay,
                start_date,
                end_date,
                args.include_content,
            )
        except requests.RequestException as exc:
            print(f"Page fetch failed: {page_number}: {exc}")
            break

        if not page_rows and not saw_older_article:
            print(f"No articles found on page {page_number}; stop.")
            break

        print(f"Fetched page {page_number}: {len(page_rows)} articles")
        rows.extend(page_rows)
        if saw_older_article:
            print(f"Reached articles older than start_date on page {page_number}; stop.")
            break
        sleep_briefly(args.min_delay, args.max_delay)

    output_path = (
        Path(args.output)
        if args.output
        else default_output_path(category, args.format, start_date, end_date)
    )
    if args.format == "csv":
        write_csv(output_path, rows)
    else:
        write_json(output_path, rows)

    print(f"Saved {len(rows)} articles to {output_path}")
    if args.summary:
        print("")
        print(summarize_rows(rows, category, args.topic))


if __name__ == "__main__":
    main()
