"""Artificial Analysis metrics with explicit units and header-based parsing."""
import os
import re

from bs4 import BeautifulSoup

from utils.data import get, http_session, number, snapshot, validate_board

EMBED_URL = "https://artificialanalysis.ai/embed/llm-performance-leaderboard"
API_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"


def parse_value(text):
    text = text.strip().replace(",", "").removeprefix("$")
    match = re.fullmatch(r"([\d.]+)\s*([kKmM]?)", text)
    return number(match[1]) * {"": 1, "k": 1e3, "m": 1e6}[match[2].lower()] if match and number(match[1]) is not None else None


def build_boards(models, definitions, method):
    boards = {}
    for name, (metric, unit, ascending) in definitions.items():
        candidates = [m for m in models if number(m.get(metric)) is not None and m[metric] >= 0]
        candidates.sort(key=lambda m: (m[metric] if ascending else -m[metric], m["model_id"]))
        rows, seen = [], set()
        for model in candidates:
            identity = model["base_id"] if name == "Intelligence" else model["model_id"]
            if identity in seen:
                continue
            seen.add(identity)
            score = model[metric]
            rank = rows[-1]["rank"] if rows and rows[-1]["score"] == score else len(rows) + 1
            rows.append({"model_id": identity, "name": model["name"] if name == "Intelligence" else model["deployment_name"],
                         "rank": rank, "score": score})
        if not rows:
            raise ValueError(f"Artificial Analysis: no values for {name}")
        board = {"scope": f"aa:{method}:{metric}", "metric": metric, "unit": unit,
                 "published_at": None, "rows": [r for r in rows if r["rank"] <= 50], "coverage": "rank<=50"}
        validate_board(board)
        boards[name] = board
    return boards


def parse_embed_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.select("table"):
        header = next((tr for tr in table.select("tr") if "API Provider" in [th.get_text(" ", strip=True) for th in tr.select("th")]), None)
        if header is None:
            continue
        names = [th.get_text(" ", strip=True) for th in header.select("th")]
        required = {"provider": "API Provider", "name": "Model", "intelligence": "Artificial Analysis Intelligence Index",
                    "cost_per_task": "Cost per Task USD", "speed": "Median Tokens/s"}
        if not all(value in names for value in required.values()):
            raise ValueError("Artificial Analysis table headers or cost units changed")
        columns = {key: names.index(value) for key, value in required.items()}
        models = []
        for tr in table.select("tr"):
            cells = tr.select("td")
            if not cells:
                continue
            if len(cells) < len(names):
                raise ValueError("Artificial Analysis table has an incomplete row")
            text = [c.get_text(" ", strip=True) for c in cells]
            link = tr.find("a", href=re.compile(r"^/models/"))
            provider_link = tr.find("a", href=re.compile(r"^/providers/"))
            if not link or not provider_link:
                raise ValueError("Artificial Analysis model or provider link is missing")
            name, provider = text[columns["name"]], text[columns["provider"]]
            identity = link["href"] + "|" + name
            models.append({"base_id": identity, "model_id": identity + "|" + provider_link["href"],
                           "name": name, "deployment_name": f"{name} ({provider})",
                           **{key: parse_value(text[columns[key]]) for key in ["intelligence", "cost_per_task", "speed"]}})
        return build_boards(models, {"Intelligence": ("intelligence", "index", False),
                                    "Speed": ("speed", "tokens/s", False),
                                    "CostPerTask": ("cost_per_task", "USD/task", True)}, "html")
    raise ValueError("Artificial Analysis performance table not found")


def parse_api(payload):
    models = []
    for row in payload["data"]:
        identity, name = row["id"], row["name"]
        models.append({"base_id": identity, "model_id": identity, "name": name, "deployment_name": name,
                       "intelligence": number(row.get("evaluations", {}).get("artificial_analysis_intelligence_index")),
                       "speed": number(row.get("median_output_tokens_per_second")),
                       "input_price": number(row.get("pricing", {}).get("price_1m_input_tokens")),
                       "output_price": number(row.get("pricing", {}).get("price_1m_output_tokens"))})
    return build_boards(models, {"Intelligence": ("intelligence", "index", False),
                                "Speed": ("speed", "tokens/s", False),
                                "InputPrice": ("input_price", "USD/1M input tokens", True),
                                "OutputPrice": ("output_price", "USD/1M output tokens", True)}, "api")


def scrape_artalanaly():
    key = os.getenv("ARTIFICIAL_ANALYSIS_API_KEY")
    with http_session() as session:
        if key:
            payload = get(session, API_URL, headers={"x-api-key": key}).json()
            return snapshot("artalanaly", "https://artificialanalysis.ai/", "official_api", parse_api(payload))
        html = get(session, EMBED_URL).text
    return snapshot("artalanaly", EMBED_URL, "public_html", parse_embed_html(html))
