# LLM Trend Observer

**简体中文** | [English](README.en.md)

持续追踪大模型的使用量、评测表现与运行成本，生成每日 Markdown 报告，并支持通过 WxPusher 和 Server酱订阅。

日报只展示重点变化、前十榜单和来源链接，每个来源最多两条摘要，不使用圆点分隔或圆点列表。单位直接放在表头；采集方式、时间、统计窗口与筛选规则保留在数据文件和项目文档中。数据缺失时仅简短标注历史数据。

## 查看报告与订阅

- [最新报告](reports/latest_report.md)
- [历史报告](reports/)
- [运行状态](https://github.com/TengJiao33/LLM_Trend_Observer/actions/workflows/daily_report.yml)
- [通过微信订阅 WxPusher 主题](https://wxpusher.zjiecode.com/wxuser/?type=2&id=43364#/follow)

工作流计划在每天北京时间 **10:17** 启动。GitHub Actions 的定时任务可能延迟；实际采集时间以快照文件为准。

## 数据来源

| 来源 | 追踪内容 | 采集方式 |
| :--- | :--- | :--- |
| [OpenRouter](https://openrouter.ai/rankings) | 平台内模型 Token 使用量 | 配置 API key 时读取上一个完整 UTC 日的官方 Data API；否则读取公开周榜 |
| [Arena](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset) | 文本、视觉、智能体、网页开发、文档、搜索、图像及视频赛道 | 固定数据集版本，读取官方 `latest` Parquet 文件的 `overall` 分类 |
| [Artificial Analysis](https://artificialanalysis.ai/) | 能力指数、输出速度、成本 | 配置 API key 时读取官方 API；否则按表头读取公开性能榜 |

Text 和 Vision 使用 Arena 的 style-controlled 版本。Agent 分数以百分比展示，其他 Arena 分数保留官方评分，区间保存在快照文件中。官方数据集没有单独提供的旧分类不会继续用过期快照补齐。

AA 网页中的 **USD/task** 表示任务成本；API 模式分别展示输入和输出的 **USD/1M tokens**。这些指标分别建立基线。能力榜区分推理设置，速度和成本榜区分模型部署及托管商。

HF Open LLM Leaderboard 已于 [2025 年 3 月正式退役](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135)，不再纳入日报。已有历史文件保留供查阅。

## 报告如何判断变化

- 保留来源的原始名次和真实模型标识；前十名包含并列条目，不强行改成连续排名。
- 同时展示名次变化、数值变化，以及适用时的相对变化。
- 标注进入或离开前十的模型；离开采集范围不等于模型下架。
- 只有指标、单位、采集范围和方法一致的快照参与比较。切换日榜与周榜、API 与网页时重新建立基线。
- 采集失败的赛道沿用最近成功数据并简短标注日期；首次采集和历史数据均隐藏变化列。

摘要筛选规则为：名次变化至少 2 位，或 Arena 分数变化至少 5 分、能力指数至少 1 分、Agent 分数至少 1 个百分点、其他数值至少 10%；基线为零时的非零变化也会单列。这些阈值用于控制信息量，不代表统计显著性。比较基线是最近一次同口径成功采集，不一定是前一天。

OpenRouter 的使用量只代表该平台，不能直接作为整个市场的占有率。不同榜单反映不同任务与评测方法，不合并为单一“最佳模型”排名。

## 本地运行

需要 Python 3.10 或更高版本；CI 使用 Python 3.12。无需安装浏览器。

```bash
git clone https://github.com/TengJiao33/LLM_Trend_Observer.git
cd LLM_Trend_Observer
python -m venv .venv
```

激活环境：Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1`；macOS/Linux 使用 `source .venv/bin/activate`。

```bash
python -m pip install -r requirements.txt
python main.py --no-notify
```

默认生成报告和更新本地历史，不发送通知。开发或试运行时可使用独立目录：

```bash
python main.py --no-notify --data-dir work/data --output-dir work/reports
python -m unittest discover -s tests -v
```

生成文件：

| 路径 | 内容 |
| :--- | :--- |
| `reports/latest_report.md` | 最新报告 |
| `reports/report_*.md` | 历史报告，文件名使用北京时间 |
| `data/*_current.json` | 本次采集的快照及指标口径 |
| `data/source_status.json` | 各来源及赛道的采集状态 |
| `data/history.json` | 最近成功快照，用于下次比较 |
| `data/backups/` | 更新前的历史备份 |

首次升级会保留旧格式历史，并为新采集口径重新建立基线，避免将旧的错误排名或模糊单位带入比较。

## 配置数据接口与推送

将 `.env.example` 复制为 `.env`，按需填写。密钥只保存在本地或 GitHub Secrets 中。

| 配置项 | 用途 |
| :--- | :--- |
| `OPENROUTER_API_KEY` | 可选；启用 [OpenRouter Data API](https://openrouter.ai/docs/cookbook/administration/data-api) 的每日使用量 |
| `ARTIFICIAL_ANALYSIS_API_KEY` | 可选；启用 [AA API](https://artificialanalysis.ai/api-reference) 的能力、速度与 Token 价格 |
| `WXPUSHER_APP_TOKEN` | WxPusher 应用 token |
| `WXPUSHER_UIDS` | 接收用户 UID，逗号分隔 |
| `WXPUSHER_TOPIC_IDS` | 订阅主题 ID，逗号分隔；与 UID 至少配置一种 |
| `SERVERCHAN_SENDKEY` | Server酱推送密钥 |

配置接口密钥后，接口失败会明确报错，不自动切换统计口径。未配置接口密钥时，公开网页模式仍可使用。

发送报告需显式启用：

```bash
python main.py --notify
```

## GitHub Actions

Fork 仓库后，在 **Settings → Secrets and variables → Actions** 中添加所需配置，并为工作流启用仓库内容写入权限。可在 **Actions → Daily LLM Trend Report → Run workflow** 手动运行。

工作流先运行回归测试，再采集和推送。来源全部失败、部分赛道缺失或已配置推送渠道报错时，运行状态会失败；已生成的报告和成功快照仍会保存，原始采集文件也会作为 Actions artifact 保留 30 天。

本地命令遵循相同退出规则。只有在主动接受不完整来源时，才使用 `--allow-partial`；此选项不会忽略推送失败。

## 数据署名

报告链接到各原始来源。Arena 数据和 OpenRouter Data API 数据遵循各自的 CC BY 4.0 署名要求；使用 AA 数据时保留 Artificial Analysis 署名。数据定义、授权条件与评测方法以各来源的官方说明为准。
