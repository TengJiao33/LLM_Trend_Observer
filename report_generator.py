import json
import os
from datetime import datetime
from compare import DeltaEngine


SOURCE_FILES = {
    "openrouter": "data/openrouter_current.json",
    "lmsys": "data/lmsys_current.json",
    "artalanaly": "data/artalanaly_current.json",
    "hf_leaderboard": "data/hf_leaderboard_current.json",
}
SOURCE_LABELS = {
    "openrouter": "OpenRouter",
    "lmsys": "LMSYS/Arena",
    "artalanaly": "Artificial Analysis",
    "hf_leaderboard": "HF Open LLM",
}
STATUS_FILE = "data/source_status.json"

CAT_MAP = {
    "Agent": "智能体",
    "Text": "文本能力",
    "Code": "编程能力",
    "WebDev": "网页开发",
    "Vision": "多模态/视觉",
    "Document": "文档理解",
    "Text-to-Image": "文生图",
    "Image Edit": "图像编辑",
    "Image-to-WebDev": "图生网页",
    "Search": "搜索增强",
    "Text-to-Video": "文生视频",
    "Image-to-Video": "图生视频",
    "Video Edit": "视频编辑",
}
AA_CAT_MAP = {
    "Intelligence": "智力/质量指数",
    "Speed": "吞吐速度",
    "Price": "价格",
}


class ReportGenerator:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.engine = DeltaEngine()

    def _format_delta(self, delta):
        if delta == "New":
            return "🆕 **New**"
        elif "↑" in delta:
            return f"🟢 {delta}"
        elif "↓" in delta:
            return f"🔴 {delta}"
        else:
            return "⚪ -"

    def _load_json(self, file_path, default):
        if not os.path.exists(file_path):
            return default

        with open(file_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)

    def _load_source_statuses(self):
        return self._load_json(STATUS_FILE, {})

    def _history_categories(self, source_name, preferred_order=None, include_extra=True):
        prefix = f"{source_name}_"
        categories = {}

        if preferred_order:
            for cat in preferred_order:
                key = f"{prefix}{cat}"
                data = self.engine.history.get(key)
                if isinstance(data, list) and data:
                    categories[cat] = data

        if not include_extra:
            return categories

        for key in sorted(self.engine.history):
            if not key.startswith(prefix):
                continue
            cat = key[len(prefix):]
            if cat in categories:
                continue
            data = self.engine.history.get(key)
            if isinstance(data, list) and data:
                categories[cat] = data

        return categories

    def _load_single_source(self, source_name):
        file_path = SOURCE_FILES[source_name]
        data = self._load_json(file_path, None)
        if data is not None:
            return data, False

        history_data = self.engine.history.get(source_name, [])
        return history_data, bool(history_data)

    def _load_multi_source(self, source_name, preferred_order=None, include_extra=True):
        file_path = SOURCE_FILES[source_name]
        data = self._load_json(file_path, None)
        if isinstance(data, dict):
            return data, False

        history_data = self._history_categories(source_name, preferred_order, include_extra)
        return history_data, bool(history_data)

    def _build_status_md(self, statuses, fallback_sources):
        if not statuses and not fallback_sources:
            return ""

        lines = ["## 🧭 数据源状态", ""]
        for source_name, label in SOURCE_LABELS.items():
            status = statuses.get(source_name)
            if status and status.get("success") and status.get("has_current"):
                lines.append(f"- ✅ {label}: 本次抓取成功")
            elif source_name in fallback_sources:
                lines.append(f"- ⚠️ {label}: 本次抓取缺失，报告沿用历史数据")
            elif status and not status.get("success"):
                lines.append(f"- ❌ {label}: 本次抓取失败，暂无可用数据")
            elif status:
                lines.append(f"- ⚠️ {label}: 本次抓取未产出数据文件")

        lines.append("")
        lines.append("---")
        lines.append("")
        return "\n".join(lines)

    def generate(self):
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.output_dir, filename)

        statuses = self._load_source_statuses()
        fallback_sources = set()

        or_data, used_fallback = self._load_single_source("openrouter")
        if used_fallback:
            fallback_sources.add("openrouter")

        lmsys_data, used_fallback = self._load_multi_source(
            "lmsys", preferred_order=CAT_MAP.keys(), include_extra=False
        )
        if used_fallback:
            fallback_sources.add("lmsys")

        aa_data, used_fallback = self._load_multi_source(
            "artalanaly", preferred_order=AA_CAT_MAP.keys(), include_extra=False
        )
        if used_fallback:
            fallback_sources.add("artalanaly")

        hf_data, used_fallback = self._load_single_source("hf_leaderboard")
        if used_fallback:
            fallback_sources.add("hf_leaderboard")

        # Get Deltas
        or_reports = self.engine.compare("openrouter", or_data)
        
        lmsys_categories_reports = {}
        if isinstance(lmsys_data, dict):
            for cat, data in lmsys_data.items():
                lmsys_categories_reports[cat] = self.engine.compare(f"lmsys_{cat}", data)
        else:
            lmsys_categories_reports["Overall"] = self.engine.compare("lmsys", lmsys_data)

        aa_categories_reports = {}
        if isinstance(aa_data, dict):
            for cat, data in aa_data.items():
                aa_categories_reports[cat] = self.engine.compare(f"artalanaly_{cat}", data)

        hf_reports = self.engine.compare("hf_leaderboard", hf_data)

        # --- 构建显著变动摘要（放在报告最前面） ---
        # 收集所有来源的变动，附带榜单名称
        tagged_reports = []
        for r in or_reports:
            tagged_reports.append({**r, "_source": "OpenRouter"})
        for cat, reports in lmsys_categories_reports.items():
            label = f"LMSYS {cat}"
            for r in reports:
                tagged_reports.append({**r, "_source": label})
        for cat, reports in aa_categories_reports.items():
            label = f"AA {AA_CAT_MAP.get(cat, cat)}"
            for r in reports:
                tagged_reports.append({**r, "_source": label})
        for r in hf_reports:
            tagged_reports.append({**r, "_source": "HF Open LLM"})

        # 筛选：新模型、大幅上升(>=2)、大幅下跌(>=2)
        new_models = [(r['model_id'], r['_source']) for r in tagged_reports if r['delta'] == "New"]
        big_ups = [(r['model_id'], r['delta'], r['_source']) for r in tagged_reports if "↑" in r['delta'] and int(r['delta'][1:]) >= 2]
        big_downs = [(r['model_id'], r['delta'], r['_source']) for r in tagged_reports if "↓" in r['delta'] and int(r['delta'][1:]) >= 2]

        highlights_md = ""
        has_highlights = new_models or big_ups or big_downs

        if has_highlights:
            highlights_md += "## 🔍 今日显著变动\n\n"
            if new_models:
                highlights_md += "### 🆕 新上榜模型\n"
                for m, src in new_models[:8]:
                    highlights_md += f"- `{m}` — *{src}*\n"
            if big_ups:
                highlights_md += "\n### 📈 排名大幅上升 (≥2 位)\n"
                for m, delta, src in big_ups[:8]:
                    highlights_md += f"- `{m}` ({self._format_delta(delta)}) — *{src}*\n"
            if big_downs:
                highlights_md += "\n### 📉 排名大幅下跌 (≥2 位)\n"
                for m, delta, src in big_downs[:8]:
                    highlights_md += f"- `{m}` ({self._format_delta(delta)}) — *{src}*\n"
            highlights_md += "\n---\n\n"
        else:
            highlights_md += "## 🔍 今日显著变动\n本期排名相对稳定，未检测到显著异常变动。\n\n---\n\n"

        # --- 构建完整报告 ---
        md = f"""# 🤖 大模型今日趋势-{now.strftime('%m-%d')}
> 📅 **生成时间**: `{timestamp_str}`
> 📊 **数据源**: [OpenRouter](https://openrouter.ai/rankings) | [LMSYS Arena](https://lmarena.ai/leaderboard) | [HF Open LLM](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard) | [Artificial Analysis](https://artificialanalysis.ai/)

---

"""
        md += self._build_status_md(statuses, fallback_sources)

        # 显著变动放在最前面
        md += highlights_md

        # OpenRouter Section
        md += """## 🚀 OpenRouter 排行榜
*基于 OpenRouter 平台真实部署与调用量统计*

| 排名 | 模型 ID | 使用量 (Tokens) | 增长率 | 变动 |
| :--- | :--- | :--- | :--- | :--- |
"""
        # OpenRouter 排名可能跳号（网站原始数据），重新编号确保连续
        for idx, item in enumerate(or_reports[:10], 1):
            delta_styled = self._format_delta(item['delta'])
            curr_item = next((x for x in or_data if x['model_id'] == item['model_id']), {})
            tokens = curr_item.get('tokens', '-')
            growth = curr_item.get('growth', '-')
            md += f"| {idx} | `{item['model_id']}` | {tokens} | {growth} | {delta_styled} | \n"

        # LMSYS Section (Multi-Category)
        md += "\n---\n"
        for cat, reports in lmsys_categories_reports.items():
            if not reports: continue
            display_name = f"{cat} ({CAT_MAP.get(cat, '综合')})"
            
            md += f"""
## 🏆 LMSYS {display_name}
*基于众测竞技场 Elo 分数统计*

| 排名 | 模型名称 | 分数 | 区间/误差 | 变动 |
| :--- | :--- | :--- | :--- | :--- |
"""
            # 获取该赛道的原始数据以提取置信区间等
            cat_raw_data = lmsys_data.get(cat, []) if isinstance(lmsys_data, dict) else lmsys_data
            
            for item in reports[:10]:
                delta_styled = self._format_delta(item['delta'])
                curr_item = next((x for x in cat_raw_data if x['model_id'] == item['model_id']), {})
                votes = curr_item.get('votes', '-')
                md += f"| {item['rank']} | **{item['model_id']}** | {item['score']} | {votes} | {delta_styled} | \n"

        # Artificial Analysis Section
        if aa_categories_reports:
            md += "\n---\n"
            for cat, reports in aa_categories_reports.items():
                if not reports: continue
                display_name = AA_CAT_MAP.get(cat, cat)
                
                md += f"""
## 💎 Artificial Analysis {display_name}
*基于独立基准测试与性能追踪*

| 排名 | 模型名称 (托管商) | 数值 | 变动 |
| :--- | :--- | :--- | :--- |
"""
                cat_raw_data = aa_data.get(cat, [])
                for item in reports[:10]:
                    delta_styled = self._format_delta(item['delta'])
                    md += f"| {item['rank']} | {item['model_id']} | `{item['score']}` | {delta_styled} | \n"

        # HF Open LLM Leaderboard Section
        if hf_reports:
            md += "\n---\n"
            md += f"""
## 🤗 Hugging Face Open LLM 排行榜
*基于开源模型综合评估指标 (Average Score) 统计*
> 💡 **数据说明**: 本章节数据来自 HF 官方 `open-llm-leaderboard/contents` 数据集后端，包含所有已评估模型（共 4576 个）。相比于网页端 "Archived" 的快照，API 数据更全面且包含了一些未在前端置顶的模型。

| 排名 | 模型名称 | 平均分 | 变动 |
| :--- | :--- | :--- | :--- |
"""
            for item in hf_reports[:10]:
                delta_styled = self._format_delta(item['delta'])
                md += f"| {item['rank']} | **{item['model_id']}** | {item['score']} | {delta_styled} | \n"

        md += "\n---\n*Report generated by LLM Trend Observer System*"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        
        # Also update a 'latest_report.md' for constants links
        with open(os.path.join(self.output_dir, "latest_report.md"), "w", encoding="utf-8") as f:
            f.write(md)

        print(f"Report generated: {filepath}")
        return filepath


