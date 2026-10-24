"""I/O for dated, explicitly scoped leaderboard snapshots."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_session():
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers["User-Agent"] = "LLM-Trend-Observer/2.0"
    return session


def get(session, url, **kwargs):
    response = session.get(url, timeout=(10, 40), **kwargs)
    response.raise_for_status()
    return response


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def snapshot(source, url, method, boards, **metadata):
    return {"schema_version": 2, "source": source, "url": url, "method": method,
            "fetched_at": utc_now(), "boards": boards, "errors": {}, **metadata}


def validate_board(board):
    rows = board.get("rows", [])
    if not rows:
        raise ValueError("Leaderboard is empty")
    if not all(board.get(k) for k in ["scope", "metric", "unit"]):
        raise ValueError("Leaderboard metric, unit or scope is missing")
    ids = [row.get("model_id") for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate model identifiers")
    for row in rows:
        rank = number(row.get("rank"))
        if rank is None or rank < 1 or not rank.is_integer() or number(row.get("score")) is None:
            raise ValueError("Invalid rank or score")
