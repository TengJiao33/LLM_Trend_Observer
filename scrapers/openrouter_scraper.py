"""OpenRouter daily API, or the complete weekly public leaderboard."""
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from bs4 import BeautifulSoup

from utils.data import get, http_session, snapshot, validate_board

RANKINGS_URL = "https://openrouter.ai/rankings?view=week"
API_URL = "https://openrouter.ai/api/v1/datasets/rankings-daily"


def parse_tokens(text):
    match = re.fullmatch(r"([\d,.]+)\s*([KMBT]?)\s*tokens", text.strip(), re.I)
    if not match:
        raise ValueError("Unrecognized OpenRouter token count")
    return int(float(match[1].replace(",", "")) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[match[2].upper()])


def parse_rankings_html(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select('[data-testid="model-rankings-leaderboard-row"]')
    rows = []
    for card in cards:
        children = card.find_all(recursive=False)
        rank_text = children[0].get_text("", strip=True) if children else ""
        match = re.fullmatch(r"(\d+)\.", rank_text)
        link = card.find("a", href=re.compile(r"^/[^/]+/[^/?#]+"))
        tokens = next((s for s in card.stripped_strings if re.fullmatch(r"[\d,.]+\s*[KMBT]?\s*tokens", s, re.I)), None)
        if not match or not link or not tokens:
            raise ValueError("OpenRouter row is missing rank, model link or usage")
        growth_node = card.find(attrs={"title": re.compile("Change in tokens", re.I)})
        growth = growth_node.get_text("", strip=True) if growth_node else "unknown"
        if growth_node and growth.endswith("%"):
            growth = ("-" if growth_node.select_one('[class*="negative"]') else "+") + growth.lstrip("+-")
        model_id = unquote(link["href"].split("?", 1)[0].strip("/"))
        rows.append({"rank": int(match[1]), "model_id": model_id,
                     "name": link.get_text(" ", strip=True), "score": parse_tokens(tokens),
                     "tokens_display": tokens, "growth": growth})
    rows.sort(key=lambda r: r["rank"])
    if len(rows) < 10 or [r["rank"] for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("OpenRouter leaderboard is incomplete or contains duplicate ranks")
    board = {"scope": "openrouter:html:week", "metric": "tokens", "unit": "tokens",
             "published_at": None, "window": "Public weekly leaderboard / last week",
             "rows": rows[:50], "coverage": "top50" if len(rows) >= 50 else f"top{len(rows)}"}
    validate_board(board)
    return board


def parse_daily_api(payload, day):
    meta = payload.get("meta", {})
    if meta.get("start_date") != day or meta.get("end_date") != day:
        raise ValueError("OpenRouter API returned an unexpected date window")
    rows = []
    for row in payload["data"]:
        if row["date"] != day:
            raise ValueError("OpenRouter API returned a row outside the requested day")
        if row["model_permaslug"] == "other":
            continue
        tokens = int(row["total_tokens"])
        if tokens <= 0:
            raise ValueError("Invalid OpenRouter token count")
        rows.append({"model_id": row["model_permaslug"], "name": row["model_permaslug"], "score": tokens})
    rows.sort(key=lambda r: (-r["score"], r["model_id"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    board = {"scope": "openrouter:api:utc_day", "metric": "tokens", "unit": "tokens",
             "published_at": day, "window": f"{day} 00:00–24:00 UTC",
             "rows": rows, "coverage": "top50", "as_of": meta.get("as_of")}
    validate_board(board)
    return board


def scrape_openrouter():
    key = os.getenv("OPENROUTER_API_KEY")
    with http_session() as session:
        if key:
            day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
            payload = get(session, API_URL, headers={"Authorization": f"Bearer {key}"},
                          params={"start_date": day, "end_date": day}).json()
            return snapshot("openrouter", "https://openrouter.ai/rankings", "official_api",
                            {"Usage": parse_daily_api(payload, day)}, api_meta=payload["meta"])
        html = get(session, RANKINGS_URL).text
    return snapshot("openrouter", RANKINGS_URL, "public_html", {"Usage": parse_rankings_html(html)})
