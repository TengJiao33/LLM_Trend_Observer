import json
import os
from datetime import datetime
from compare import DeltaEngine

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

    def generate(self):
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        filename = f"report_{now.strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.output_dir, filename)

        # Load Current Data
        or_data = []
        lmsys_data = {}
        
        if os.path.exists("data/openrouter_current.json"):
            with open("data/openrouter_current.json", "r", encoding="utf-8") as f:
                or_data = json.load(f)
        
        if os.path.exists("data/lmsys_current.json"):
            with open("data/lmsys_current.json", "r", encoding="utf-8") as f:
                lmsys_data = json.load(f)

        aa_data = {}
        if os.path.exists("data/artalanaly_current.json"):
            with open("data/artalanaly_current.json", "r", encoding="utf-8") as f:
                aa_data = json.load(f)

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

        # Build Markdown
        md = f"""# 🤖 大模型今日趋势-{now.strftime('%m-%d')}
base_url = "https://artificialanalysis.ai/"
> 📅 **生成时间**: `{timestamp_str}`
> 📊 **数据源**: [OpenRouter](https://openrouter.ai/rankings) | [LMSYS Arena](https://lmarena.ai/leaderboard) | [Artificial Analysis](https://artificialanalysis.ai/)

---

## 🚀 OpenRouter 排行榜
*基于 OpenRouter 平台真实部署与调用量统计*

| 排名 | 模型 ID | 使用量 (Tokens) | 增长率 | 变动 |
| :--- | :--- | :--- | :--- | :--- |
"""
        for item in or_reports[:10]:
            delta_styled = self._format_delta(item['delta'])
            curr_item = next((x for x in or_data if x['model_id'] == item['model_id']), {})
            tokens = curr_item.get('tokens', '-')
            growth = curr_item.get('growth', '-')
            md += f"| {item['rank']} | `{item['model_id']}` | {tokens} | {growth} | {delta_styled} | \n"

        # LMSYS Section (Multi-Category)
        md += "\n---\n"
        for cat, reports in lmsys_categories_reports.items():
            if not reports: continue
            
            # 赛道名称翻译
            CAT_MAP = {
                "Text": "文本能力",
                "Code": "编程能力",
                "Vision": "多模态/视觉",
                "Text-to-Image": "文生图",
                "Image Edit": "图像编辑",
                "Search": "搜索增强",
                "Text-to-Video": "文生视频",
                "Image-to-Video": "图生视频"
            }
            display_name = f"{cat} ({CAT_MAP.get(cat, '综合')})"
            
            md += f"""
## 🏆 LMSYS {display_name}
*基于众测竞技场 Elo 分数统计*

| 排名 | 模型名称 | Elo 分数 | 投票数 | 变动 |
| :--- | :--- | :--- | :--- | :--- |
"""
            # 获取该赛道的原始数据以提取投票数等
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
                
                AA_CAT_MAP = {
                    "Intelligence": "智力/质量指数",
                    "Speed": "吞吐速度 (Tokens/s)",
                    "Price": "价格 (USD/1M Tokens)"
                }
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

        # Special Analysis Section
        md += "\n--- \n\n## 🔍 显著变动与新模型\n"
        
        # 聚合所有赛道的报告进行分析
        all_lmsys_reports = []
        for r_list in lmsys_categories_reports.values():
            all_lmsys_reports.extend(r_list)
            
        combined_reports = or_reports + all_lmsys_reports
        for r_list in aa_categories_reports.values():
            combined_reports.extend(r_list)
        
        new_models = [r['model_id'] for r in combined_reports if r['delta'] == "New"]
        big_ups = [r['model_id'] for r in combined_reports if "↑" in r['delta'] and int(r['delta'][1:]) >= 2]
        
        if new_models:
            md += "### 🆕 新上榜模型\n"
            for m in new_models[:5]:
                md += f"- `{m}`\n"
        
        if big_ups:
            md += "\n### 📈 表现强劲 (排名上升 >= 2)\n"
            for m in big_ups[:5]:
                md += f"- `{m}`\n"

        if not new_models and not big_ups:
            md += "本期排名相对稳定，未检测到显著异常变动。\n"

        md += "\n---\n*Report generated by LLM Trend Observer System*"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md)
        
        # Also update a 'latest_report.md' for constants links
        with open(os.path.join(self.output_dir, "latest_report.md"), "w", encoding="utf-8") as f:
            f.write(md)

        print(f"Report generated: {filepath}")
        return filepath


