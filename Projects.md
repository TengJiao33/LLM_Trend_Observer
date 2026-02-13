# LLM Trend Observer 项目文档

本项目旨在建立一个自动化系统，持续监测全球顶级大模型排行榜（LMSYS Chatbot Arena 和 OpenRouter Rankings）的趋势变化，并通过微信/邮件实时推送。

## 🚀 目前已完成的工作

### 1. 基础环境配制 (P1)
- **虚拟环境**：已建立 `.venv` 并安装全部依赖。
- **环境激活**：在终端使用 `.\.venv\Scripts\Activate.ps1` 激活。
- **依赖列表**：`requests`, `pandas`, `playwright`, `beautifulsoup4`, `python-dotenv`。

### 2. 多源数据抓取 (P2 & P3) - 已增强
- **OpenRouter 排行榜**：
    - **逻辑**：Playwright + 结构化正则提取。
    - **新功能**：除了排名，现在还捕获 **Token 使用量** 和 **增长率**。
- **LMSYS Chatbot Arena**：
    - **逻辑**：Playwright 直接访问 `lmarena.ai`。
    - **新功能**：除了 Elo 分数，现在还捕获 **投票数 (Votes)**。

### 3. 数据比对与报告引擎 (P4)
- **对比引擎** (`compare.py`)：计算排名 Delta (↑/↓) 和 "New" 标签。
- **报告生成** (`report_generator.py`)：自动生成美观的 Markdown 报告，包含多维指标和原网页直达链接。
- **主调度器** (`main.py`)：一键运行抓取 -> 对比 -> 生成报告，实现了完整闭环。

## 📁 核心脚本与接口

| 脚本/接口 | 位置 | 功能描述 | 状态 |
| :--- | :--- | :--- | :--- |
| **主控程序** | `main.py` | 驱动整个流水线 | 稳定 ✅ |
| **OpenRouter 爬虫** | `scrapers/openrouter_scraper.py` | 提取使用量与增长率 | 稳定 ✅ |
| **LMSYS 爬虫** | `scrapers/lmsys_scraper.py` | 提取 Elo 与投票数 | 稳定 ✅ |
| **报告生成器** | `report_generator.py` | 制作 MD 技术报告 | 稳定 ✅ |

## 🛠️ 待开发的模块与问题

- **待开发模块**：
    - **P5: 通知推送系统**：目前 `main.py` 中留有占位符，需集成 WXPusher 或 Server酱。
    - **P6: 自动化集成**：完善 GitHub Actions 的 Cron 触发配置，确保每日自动更新报告。
- **待解决问题**：
    - 进一步处理 `data/history.json` 的自动备份，防止频繁抓取导致的历史污染。
