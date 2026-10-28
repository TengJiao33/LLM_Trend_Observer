"""Daily highlights and leaderboards without collection-process boilerplate."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from compare import DeltaEngine
from scrapers.lmsys_scraper import CONFIGS

LABELS = {"openrouter": "OpenRouter", "lmsys": "Arena", "artalanaly": "Artificial Analysis"}
BOARD_LABELS = {"Usage": "模型调用量", "Agent": "智能体", "Text": "文本", "WebDev": "网页开发",
                "Vision": "视觉", "Document": "文档", "Search": "搜索", "Text-to-Image": "文生图",
                "Image Edit": "图像编辑", "Text-to-Video": "文生视频", "Image-to-Video": "图生视频",
                "Video Edit": "视频编辑", "Intelligence": "能力指数", "Speed": "输出速度",
                "CostPerTask": "任务成本", "InputPrice": "输入 Token 价格", "OutputPrice": "输出 Token 价格"}
UNITS = {"proportion": "百分比", "rating": "Arena 分数", "index": "能力指数", "tokens": "Tokens",
         "tokens/s": "输出 Tokens/s", "USD/task": "USD/任务", "USD/1M input tokens": "USD/百万输入 Tokens",
         "USD/1M output tokens": "USD/百万输出 Tokens"}


def escape(value):
    text = str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return text.translate(str.maketrans({"·": " ", "•": " ", "●": " ", "∙": " ", "・": " "}))


def format_value(value, unit):
    if value is None:
        return "—"
    if unit == "proportion":
        return f"{value * 100:.2f}%"
    if unit == "rating":
        return f"{value:,.1f}"
    if unit == "tokens":
        for suffix, scale in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
            if abs(value) >= scale:
                return f"{value / scale:.3g}{suffix}"
    return f"{value:,.4f}".rstrip("0").rstrip(".")


def rank_delta(row, state):
    if state == "fallback":
        return "未知"
    if state == "baseline":
        return "基线"
    if row["change"] == "entered":
        return "新入榜"
    delta = row["rank_delta"]
    return f"↑{delta}" if delta > 0 else f"↓{-delta}" if delta < 0 else "0"


def value_delta(row, unit):
    delta = row["score_delta"]
    if delta is None:
        return "未知"
    if unit == "proportion":
        return f"{delta * 100:+.2f} pp"
    text = ("+" if delta > 0 else "") + format_value(delta, unit)
    if row["relative_delta"] is not None and unit not in ["index", "rating"]:
        text += f" ({row['relative_delta']:+.1%})"
    return text


def noteworthy(row, board):
    if row["change"] == "entered":
        return True
    if row["rank_delta"] is None:
        return False
    if abs(row["rank_delta"]) >= 2:
        return True
    threshold = {"rating": 5, "index": 1, "proportion": 0.01}.get(board["unit"])
    if threshold is not None:
        return abs(row["score_delta"]) >= threshold
    return abs(row["relative_delta"]) >= 0.1 if row["relative_delta"] is not None else row["score_delta"] != 0


class ReportGenerator:
    def __init__(self, output_dir="reports", engine=None):
        self.output_dir = Path(output_dir)
        self.engine = engine or DeltaEngine()
        self.report_date = None

    def generate(self, current, statuses):
        now = datetime.now(timezone(timedelta(hours=8)))
        self.report_date = now.strftime("%Y-%m-%d")
        selections, missing = [], []
        for source in LABELS:
            fresh = current.get(source, {}).get("boards", {})
            history = self.engine.previous_boards(source)
            if not fresh and not history:
                missing.append(LABELS[source])
                continue
            # Retired or unidentifiable legacy categories never reappear as fallback.
            expected = list(CONFIGS) if source == "lmsys" else ["Usage"] if source == "openrouter" else list(fresh or history)
            for name in expected:
                board = fresh.get(name) or history.get(name)
                if board is None:
                    missing.append(f"{LABELS[source]} / {BOARD_LABELS.get(name, name)}")
                    continue
                is_fresh = name in fresh
                selections.append((source, name, board, self.engine.compare(source, name, board, is_fresh)))
        lines = [f"# 大模型趋势日报 {self.report_date}", ""]
        if missing:
            lines += ["暂无数据：" + "、".join(map(escape, missing)), ""]
        lines += ["## 重点变化", ""]
        highlights = {source: [] for source in LABELS}
        for source, name, board, comparison in selections:
            if comparison["state"] != "comparable":
                continue
            label = f"{LABELS[source]} {BOARD_LABELS.get(name, name)}"
            for row in (r for r in comparison["rows"] if r["rank"] <= 10):
                if noteworthy(row, board):
                    if row["change"] == "entered":
                        detail = f"进入前十，现第 {row['rank']} 名"
                    else:
                        changes = []
                        if row["rank_delta"]:
                            changes.append(f"排名 {rank_delta(row, 'comparable')}，现第 {row['rank']} 名")
                        if row["score_delta"]:
                            changes.append(f"变化 {value_delta(row, board['unit'])}")
                        detail = "；".join(changes)
                    highlights[source].append(f"{escape(label)}：{escape(row['name'])}，{detail}")
            for row in comparison["departures"]:
                destination = f"，现第 {row['new_rank']} 名" if row["new_rank"] else ""
                highlights[source].append(f"{escape(label)}：{escape(row['name'])} 离开前十（原第 {row['old_rank']} 名{destination}）")
        comparable = sum(c["state"] == "comparable" for _, _, _, c in selections)
        if any(highlights.values()):
            for source_highlights in highlights.values():
                for highlight in source_highlights[:2]:
                    lines += [highlight, ""]
        elif comparable:
            lines += ["暂无明显变化", ""]
        else:
            lines += ["暂无可比数据", ""]
        for source, name, board, comparison in selections:
            lines += [f"## {escape(LABELS[source])} {escape(BOARD_LABELS.get(name, name))}", ""]
            state = comparison["state"]
            if state == "fallback":
                date = (board.get("fetched_at") or "日期未知")[:10]
                lines += [f"本次未更新，显示 {escape(date)} 历史数据", ""]
            unit = escape(UNITS.get(board["unit"], board["unit"]))
            changes_header = " 名次变化 | 数值变化 |" if state == "comparable" else ""
            changes_separator = " :--- | :--- |" if state == "comparable" else ""
            lines += [f"| 排名 | 模型 | {unit} |{changes_header}",
                      f"| ---: | :--- | ---: |{changes_separator}"]
            for row in (r for r in comparison["rows"] if r["rank"] <= 10):
                model_label = escape(row["name"])
                if source == "openrouter" and "/" in row["model_id"]:
                    model_label = f"[{escape(row['model_id'])}](https://openrouter.ai/{quote(row['model_id'], safe='/:')})"
                changes = f" {rank_delta(row, state)} | {value_delta(row, board['unit'])} |" if state == "comparable" else ""
                lines.append(f"| {row['rank']} | {model_label} | {format_value(row['score'], board['unit'])} |{changes}")
            lines.append("")
        openrouter_license = " ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))" if current.get("openrouter", {}).get("method") == "official_api" else ""
        lines += ["来源：[OpenRouter](https://openrouter.ai/rankings)" + openrouter_license + " | "
                  "[Arena](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset) "
                  "([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)) | "
                  "[Artificial Analysis](https://artificialanalysis.ai/)", ""]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines)
        path = self.output_dir / f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
        path.write_text(text, encoding="utf-8")
        (self.output_dir / "latest_report.md").write_text(text, encoding="utf-8")
        return str(path)
