"""Arena's official, revision-pinned Parquet snapshots."""
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

import pyarrow.parquet as pq

from utils.data import get, http_session, number, snapshot, validate_board

DATASET = "lmarena-ai/leaderboard-dataset"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET}"
CONFIGS = {
    "Agent": "agent", "Text": "text_style_control", "WebDev": "webdev",
    "Vision": "vision_style_control", "Document": "document", "Search": "search",
    "Text-to-Image": "text_to_image", "Image Edit": "image_edit",
    "Text-to-Video": "text_to_video", "Image-to-Video": "image_to_video",
    "Video Edit": "video_edit",
}


def parse_arena_rows(rows, config):
    overall = [r for r in rows if r.get("category") == "overall"]
    dates = {r.get("leaderboard_publish_date") for r in overall}
    if not overall or len(dates) != 1 or None in dates:
        raise ValueError(f"{config}: missing overall category or inconsistent publication dates")
    agent = config == "agent"
    result = []
    for row in overall:
        score = number(row.get("score" if agent else "rating"))
        rank = number(row.get("rank"))
        if score is None or rank is None or not rank.is_integer() or not row.get("model_name"):
            raise ValueError(f"{config}: invalid model, score or rank")
        result.append({"model_id": row["model_name"], "name": row["model_name"],
                       "rank": int(rank), "score": score,
                       "ci_low": number(row.get("score_ci_lower" if agent else "rating_lower")),
                       "ci_high": number(row.get("score_ci_upper" if agent else "rating_upper")),
                       "votes": row.get("session_count" if agent else "vote_count"),
                       "organization": row.get("organization"), "license": row.get("license")})
    result.sort(key=lambda r: (r["rank"], r["model_id"]))
    board = {"scope": f"arena:{config}:overall", "metric": "agent_score" if agent else "arena_rating",
             "unit": "proportion" if agent else "rating", "published_at": next(iter(dates)),
             "rows": [r for r in result if r["rank"] <= 50], "coverage": "rank<=50", "population": len(result)}
    validate_board(board)
    return board


def _fetch_config(config, paths, revision):
    files = sorted(p for p in paths if p.startswith(config + "/latest-") and p.endswith(".parquet"))
    if not files:
        raise ValueError(f"{config}: no latest Parquet files in official dataset")
    rows = []
    with http_session() as session:
        for path in files:
            content = get(session, f"{DATASET_URL}/resolve/{revision}/{path}").content
            rows.extend(pq.read_table(io.BytesIO(content)).to_pylist())
    return parse_arena_rows(rows, config)


def scrape_lmsys_hf():
    with http_session() as session:
        metadata = get(session, f"https://huggingface.co/api/datasets/{DATASET}").json()
    revision = metadata["sha"]
    paths = [item["rfilename"] for item in metadata["siblings"]]
    boards, errors = {}, {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        tasks = {executor.submit(_fetch_config, config, paths, revision): name for name, config in CONFIGS.items()}
        for future in as_completed(tasks):
            name = tasks[future]
            try:
                boards[name] = future.result()
            except Exception as exc:
                errors[name] = str(exc)
    if not boards:
        raise ValueError("Arena: no categories available from official dataset")
    return snapshot("lmsys", DATASET_URL, "official_dataset",
                    {name: boards[name] for name in CONFIGS if name in boards}, revision=revision, errors=errors)
