import asyncio
import json
import os
from datetime import datetime

from playwright.async_api import async_playwright


ARENA_URL = "https://arena.ai/leaderboard"

OVERVIEW_CATEGORIES = [
    "Agent",
    "Text",
    "WebDev",
    "Vision",
    "Document",
    "Text-to-Image",
    "Image Edit",
    "Image-to-WebDev",
    "Search",
    "Text-to-Video",
    "Image-to-Video",
    "Video Edit",
]


def _is_rank(value):
    return value.strip().isdigit()


def _clean_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()]


def _extract_overview_blocks(body_text):
    lines = _clean_lines(body_text)
    categories_data = {}

    try:
        start = lines.index("Edit View") + 1
    except ValueError:
        try:
            start = lines.index("Leaderboard Overview") + 1
        except ValueError:
            start = 0

    i = start
    while i < len(lines):
        line = lines[i]

        if line.endswith("Arena Overview") and i > start:
            break

        if line not in OVERVIEW_CATEGORIES:
            i += 1
            continue

        category_name = line
        j = i + 1
        while j < len(lines) and not _is_rank(lines[j]):
            if lines[j] == "View all" or lines[j] in OVERVIEW_CATEGORIES:
                break
            j += 1

        leaderboard = []
        while j + 2 < len(lines) and _is_rank(lines[j]):
            rank = int(lines[j])
            model_id = lines[j + 1]
            score = lines[j + 2]
            interval = "-"
            j += 3

            if (
                j < len(lines)
                and not _is_rank(lines[j])
                and lines[j] != "View all"
                and lines[j] not in OVERVIEW_CATEGORIES
            ):
                interval = lines[j]
                j += 1

            leaderboard.append(
                {
                    "rank": rank,
                    "model_id": model_id,
                    "score": score,
                    "votes": interval,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            if len(leaderboard) >= 10:
                break

        if leaderboard:
            categories_data[category_name] = leaderboard

        i = max(j, i + 1)

    return categories_data


async def _extract_text_matrix_tables(page):
    categories_data = {}
    tables = await page.locator("table").all()
    print(f"Found {len(tables)} tables.")

    for table in tables:
        headers = [h.strip() for h in await table.locator("th").all_inner_texts()]
        if len(headers) < 2 or "Model" not in headers[0]:
            continue

        rows = await table.locator("tr").all()
        for col_idx, header in enumerate(headers[1:], start=1):
            category_name = "Text" if header == "Overall" else f"Text {header}"
            leaderboard = []

            for row in rows[1:]:
                cells = [c.strip() for c in await row.locator("td").all_inner_texts()]
                if len(cells) <= col_idx or not cells[0] or not _is_rank(cells[col_idx]):
                    continue

                leaderboard.append(
                    {
                        "rank": int(cells[col_idx]),
                        "model_id": cells[0],
                        "score": "-",
                        "votes": "-",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            if leaderboard:
                categories_data[category_name] = sorted(
                    leaderboard, key=lambda item: item["rank"]
                )[:10]

    return categories_data


async def scrape_lmsys_hf():
    print("Starting LMSYS/Arena Scrape...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            print(f"Navigating to {ARENA_URL}...")
            await page.goto(ARENA_URL, wait_until="networkidle", timeout=120000)
            await page.wait_for_selector("text=Leaderboard Overview", timeout=60000)
            await asyncio.sleep(5)

            body_text = await page.locator("body").inner_text()
            categories_data = _extract_overview_blocks(body_text)

            if categories_data:
                print(
                    "Extracted Arena overview categories: "
                    + ", ".join(f"{cat}({len(items)})" for cat, items in categories_data.items())
                )
            else:
                print("Overview extraction failed. Falling back to table matrix parser...")
                categories_data = await _extract_text_matrix_tables(page)

            if categories_data:
                os.makedirs("data", exist_ok=True)
                with open("data/lmsys_current.json", "w", encoding="utf-8") as f:
                    json.dump(categories_data, f, indent=4, ensure_ascii=False)
                return True

            await page.screenshot(path="lmsys_error_screenshot.png")
            content = await page.content()
            with open("lmsys_error_debug.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Failed to extract Arena data. Screenshot and HTML saved for debugging.")
            return False

        except Exception as e:
            print(f"Error during LMSYS/Arena scrape: {e}")
            return False
        finally:
            await browser.close()
