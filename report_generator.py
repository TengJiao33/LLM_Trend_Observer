"""Concise reports with observation dates, comparable deltas and explicit gaps."""
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
METHODS = {"official_dataset": "官方数据集", "official_api": "官方 API", "public_html": "公开网页"}
UNITS = {"proportion": "百分比", "rating": "Arena 分数", "index": "能力指数", "tokens": "Tokens",
         "tokens/s": "输出 Tokens/s", "USD/task": "USD/任务", "USD/1M input tokens": "USD/百万输入 Tokens",
         "USD/1M output tokens": "USD/百万输出 Tokens"}


def escape(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


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
        return "新进入采集范围"
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
            # Retired or unidentifiable legacy categories never reappear as fallback.
            expected = list(CONFIGS) if source == "lmsys" else ["Usage"] if source == "openrouter" else list(fresh or history)
            for name in expected:
                board = fresh.get(name) or history.get(name)
                if board is None:
                    missing.append(f"{LABELS[source]} / {BOARD_LABELS.get(name, name)}")
                    continue
                is_fresh = name in fresh
                selections.append((source, name, board, self.engine.compare(source, name, board, is_fresh)))
        lines = [f"# 大模型趋势日报 · {self.report_date}", "",
                 f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}（北京时间，UTC+8）", "",
                 "## 数据状态", "", "| 来源 | 本次采集 | 可用榜单 | 采集时间（UTC） |",
                 "| :--- | :--- | ---: | :--- |"]
        state_labels = {"ok": "成功", "partial": "部分失败", "failed": "失败"}
        for source, label in LABELS.items():
            status = statuses.get(source, {})
            lines.append(f"| {label} | {state_labels.get(status.get('state'), '未采集')} | {status.get('boards', 0)} | {status.get('fetched_at', '未知')} |")
        problems = [f"{LABELS[s]} / {name}" for s, status in statuses.items() for name in status.get("errors", {})]
        if problems:
            lines += ["", "本次存在采集缺口：" + "、".join(map(escape, problems)) + "。历史回退条目不参与变化判断。"]
        if missing:
            lines += ["", "暂无可用数据：" + "、".join(missing) + "。"]
        lines += ["", "## 变化摘要", ""]
        highlights = []
        for source, name, board, comparison in selections:
            if comparison["state"] != "comparable":
                continue
            label = f"{LABELS[source]} / {BOARD_LABELS.get(name, name)}"
            for row in (r for r in comparison["rows"] if r["rank"] <= 10):
                if noteworthy(row, board):
                    highlights.append(f"- {escape(label)}：{escape(row['name'])}；名次 {rank_delta(row, 'comparable')}；数值变化 {value_delta(row, board['unit'])}。")
            for row in comparison["departures"]:
                destination = f"现第 {row['new_rank']} 名" if row["new_rank"] else "已离开本次采集范围，不能据此判断下架"
                highlights.append(f"- {escape(label)}：{escape(row['name'])} 离开前十（原第 {row['old_rank']} 名；{destination}）。")
        baselines = sum(c["state"] == "baseline" for _, _, _, c in selections)
        comparable = sum(c["state"] == "comparable" for _, _, _, c in selections)
        if highlights:
            lines.extend(highlights[:12])
            if len(highlights) > 12:
                lines.append(f"另有 {len(highlights) - 12} 项变化，见下方明细。")
        elif comparable:
            lines.append("本次可比数据未触发摘要阈值。采集失败或历史回退不代表榜单稳定。")
        else:
            lines.append("本次尚无可比较的新旧快照，无法判断趋势。")
        if baselines:
            lines.append(f"本次为 {baselines} 个榜单建立新基线；首次采集或口径变化不记为新模型发布。")
        lines += ["", "摘要阈值：名次变化至少 2 位；或 Arena 分数变化至少 5 分、能力指数至少 1 分、Agent 分数至少 1 个百分点、其他数值至少 10%。这些是筛选规则，不是统计显著性检验。", ""]
        for source, name, board, comparison in selections:
            lines += [f"## {LABELS[source]} · {BOARD_LABELS.get(name, name)}", ""]
            state = comparison["state"]
            if state == "fallback":
                lines.append("**历史回退：本次没有新观测，全部变动未知。**")
            published = board.get("published_at") or "来源未提供"
            lines += [f"数据发布日期：{published}；最近成功采集：{board.get('fetched_at', '未知')}（UTC）。",
                      f"采集方式：{METHODS.get(board.get('method'), '未知')}；单位：{UNITS.get(board['unit'], board['unit'])}。"]
            if board.get("window"):
                lines.append("统计窗口：" + ("OpenRouter 公开周榜" if board["scope"] == "openrouter:html:week" else board["window"]) + "。")
            if comparison["baseline_at"] and state != "fallback":
                lines.append("比较基线：" + comparison["baseline_at"] + "（最近一次同口径成功采集）。")
            lines += ["", "| 排名 | 模型 / 部署 | 数值 | 区间 | 名次变化 | 数值变化 |",
                      "| ---: | :--- | ---: | :--- | :--- | :--- |"]
            for row in (r for r in comparison["rows"] if r["rank"] <= 10):
                interval = "—"
                model_label = escape(row["name"])
                if source == "openrouter" and "/" in row["model_id"]:
                    model_label = f"[{escape(row['model_id'])}](https://openrouter.ai/{quote(row['model_id'], safe='/:')})"
                if row.get("ci_low") is not None and row.get("ci_high") is not None:
                    interval = f"[{format_value(row['ci_low'], board['unit'])}, {format_value(row['ci_high'], board['unit'])}]"
                lines.append(f"| {row['rank']} | {model_label} | {format_value(row['score'], board['unit'])} | {interval} | {rank_delta(row, state)} | {value_delta(row, board['unit'])} |")
            lines.append("")
        lines += ["## 来源与口径", "",
                  "- [OpenRouter](https://openrouter.ai/rankings)：只反映该平台的 Token 使用量，不等同于整个市场的占有率。API 模式采用上一个完整 UTC 日；网页模式采用公开周榜，两种口径分别建立基线。",
                  "- [Arena 官方数据集](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset)：Text、Vision 使用 style control；其余为所列赛道的 overall。遵循官方名次和区间，不将单次名次波动解释为能力提升。数据许可：CC BY 4.0。",
                  "- [Artificial Analysis](https://artificialanalysis.ai/)：网页模式的 USD/task 是任务成本；API 模式单列输入和输出 USD/1M tokens。能力榜区分推理设置，速度与成本榜区分托管部署。网页数值受来源显示精度限制，显示为零不等于免费。",
                  "- HF Open LLM Leaderboard 已退役，不再进入日报；旧历史记录保留，不作为新口径的比较基线。", ""]
        if current.get("openrouter", {}).get("method") == "official_api":
            meta = current["openrouter"].get("api_meta", {})
            lines += [f"Source: OpenRouter (openrouter.ai/rankings), as of {meta.get('as_of', 'unknown')}. Licensed under CC BY 4.0.", ""]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        text = "\n".join(lines)
        path = self.output_dir / f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
        path.write_text(text, encoding="utf-8")
        (self.output_dir / "latest_report.md").write_text(text, encoding="utf-8")
        return str(path)
