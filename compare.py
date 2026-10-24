"""Compare only snapshots with matching metric, unit and collection scope."""
import shutil
from datetime import datetime, timezone
from pathlib import Path

from utils.data import read_json, write_json


class DeltaEngine:
    def __init__(self, history_file="data/history.json"):
        self.history_file = Path(history_file)
        saved = read_json(self.history_file, {})
        # Legacy rankings had ambiguous units and identities. Preserve them without
        # treating them as a valid baseline for the new collection methods.
        self.history = saved if saved.get("schema_version") == 2 else {
            "schema_version": 2, "sources": {}, "legacy": saved,
        }

    def previous_boards(self, source):
        return self.history.get("sources", {}).get(source, {}).get("boards", {})

    def compare(self, source, category, board, fresh=True):
        previous = self.previous_boards(source).get(category)
        compatible = previous is not None and all(
            previous.get(k) == board.get(k) for k in ["scope", "metric", "unit", "coverage"]
        )
        state = "fallback" if not fresh else "comparable" if compatible else "baseline"
        prev_map = {r["model_id"]: r for r in previous["rows"]} if compatible else {}
        rows = []
        for item in board["rows"]:
            row = dict(item, rank_delta=None, score_delta=None, relative_delta=None, change="unknown")
            old = prev_map.get(item["model_id"])
            if state == "comparable" and old:
                difference = item["score"] - old["score"]
                row.update(rank_delta=old["rank"] - item["rank"], score_delta=difference,
                           relative_delta=difference / abs(old["score"]) if old["score"] else None,
                           change="observed")
            elif state == "comparable":
                row["change"] = "entered"
            rows.append(row)
        departures = []
        if state == "comparable":
            current = {r["model_id"]: r for r in board["rows"]}
            visible = {r["model_id"] for r in board["rows"] if r["rank"] <= 10}
            for old in (r for r in previous["rows"] if r["rank"] <= 10):
                if old["model_id"] not in visible:
                    departures.append({"name": old["name"], "old_rank": old["rank"],
                                       "new_rank": current.get(old["model_id"], {}).get("rank")})
        return {"state": state, "rows": rows, "departures": departures,
                "baseline_at": previous.get("fetched_at") if compatible else None}

    def update_many(self, snapshots):
        valid = {key: value for key, value in snapshots.items() if value.get("boards")}
        if not valid:
            return
        if self.history_file.exists():
            backup_dir = self.history_file.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(self.history_file, backup_dir / f"history_{stamp}.json")
        sources = self.history.setdefault("sources", {})
        for source, current in valid.items():
            old_source = sources.get(source, {})
            old_boards = self.previous_boards(source) if old_source.get("method") == current.get("method") else {}
            # Missing categories keep their own last successful observation date.
            merged = {**old_boards, **current["boards"]}
            sources[source] = {**current, "boards": merged}
        write_json(self.history_file, self.history)
