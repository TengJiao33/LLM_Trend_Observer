import os
import shutil
import json
from datetime import datetime

class DeltaEngine:
    def __init__(self, history_file="data/history.json"):
        self.history_file = history_file
        self.history = self._load_history()

    def _load_history(self):
        if os.path.exists(self.history_file):
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def compare(self, source_name, current_data):
        """
        current_data: list of dicts with 'model_id' and 'rank'
        """
        prev_data = self.history.get(source_name, [])
        prev_map = {item["model_id"]: item["rank"] for item in prev_data}
        
        report = []
        for item in current_data:
            model_id = item["model_id"]
            curr_rank = int(item["rank"])
            
            if model_id not in prev_map:
                diff = "New"
            else:
                prev_rank = int(prev_map[model_id])
                shift = prev_rank - curr_rank
                if shift > 0:
                    diff = f"↑{shift}"
                elif shift < 0:
                    diff = f"↓{abs(shift)}"
                else:
                    diff = "-"
            
            report.append({
                "model_id": model_id,
                "rank": curr_rank,
                "delta": diff,
                "score": item.get("score", "-")
            })
            
        return report

    def update_history(self, source_name, current_data):
        # 备份旧的历史文件
        if os.path.exists(self.history_file):
            backup_dir = "data/backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"history_{timestamp}.json")
            shutil.copy2(self.history_file, backup_file)
            print(f"History backed up to {backup_file}")

        self.history[source_name] = current_data
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=4, ensure_ascii=False)


