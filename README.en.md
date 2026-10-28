# LLM Trend Observer

[简体中文](README.md) | **English**

Track model usage, evaluation results and operating costs. The project produces daily Markdown reports and supports subscriptions through WxPusher and ServerChan.

Reports show top-ten leaderboards, key values and source links, without change summaries, dot separators or bullet lists. Units appear in table headers. Collection methods, timestamps and windows remain in snapshot files and project documentation. Missing updates receive a short historical-data label.

## Reports and subscription

- [Latest report](reports/latest_report.md)
- [Report archive](reports/)
- [Workflow status](https://github.com/TengJiao33/LLM_Trend_Observer/actions/workflows/daily_report.yml)
- [Subscribe to the WxPusher topic through WeChat](https://wxpusher.zjiecode.com/wxuser/?type=2&id=43364#/follow)

The workflow requests a daily start at **10:17 Asia/Shanghai (02:17 UTC)**. GitHub Actions may delay scheduled runs. Refer to snapshot files for the actual collection times.

## Data sources

| Source | Coverage | Collection method |
| :--- | :--- | :--- |
| [OpenRouter](https://openrouter.ai/rankings) | Token usage on the platform | Official Data API for the previous complete UTC day when a key is configured; otherwise the public weekly leaderboard |
| [Arena](https://huggingface.co/datasets/lmarena-ai/leaderboard-dataset) | Text, vision, agents, web development, documents, search, images and video | Official `latest` Parquet files from one pinned dataset revision, filtered to `overall` |
| [Artificial Analysis](https://artificialanalysis.ai/) | Intelligence, output speed and cost | Official API when a key is configured; otherwise the public performance table, parsed by header |

Text and Vision use Arena's style-controlled subsets. Agent scores are displayed as percentages; other Arena scores retain the official ratings, with intervals kept in snapshot files. Legacy categories without a separate official dataset subset are not filled with obsolete snapshots.

The AA public table reports **USD/task**, a task cost. API mode reports input and output **USD/1M tokens** separately. These metrics have separate comparison baselines. Intelligence rankings distinguish reasoning settings; speed and cost rankings distinguish deployments and hosting providers.

The HF Open LLM Leaderboard [retired in March 2025](https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard/discussions/1135) and is no longer included in daily reports. Existing historical files remain available.

## Interpreting changes

- Original ranks and canonical model identifiers are retained. The top ten includes tied entries, without renumbering them.
- Reports show rank changes, absolute value changes and relative changes where appropriate.
- Newly observed entries are labelled in the tables. Models leaving the top ten are no longer displayed.
- Comparisons require matching metrics, units, collection coverage and methods. Changing between daily and weekly data, or between API and HTML modes, establishes a new baseline.
- A failed category falls back to its last successful observation with a short date label. Change columns are hidden for initial observations and historical data.

The baseline is the last successful comparable observation, which may be older than yesterday.

OpenRouter usage represents its platform, not the entire market. Leaderboards reflect different tasks and evaluation methods and are not merged into a single best-model ranking.

## Run locally

Python 3.10 or newer is required; CI uses Python 3.12. No browser installation is needed.

```bash
git clone https://github.com/TengJiao33/LLM_Trend_Observer.git
cd LLM_Trend_Observer
python -m venv .venv
```

Activate the environment with `.\.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux.

```bash
python -m pip install -r requirements.txt
python main.py --no-notify
```

By default, the command generates a report and updates local history without sending notifications. Use separate directories for development or previews:

```bash
python main.py --no-notify --data-dir work/data --output-dir work/reports
python -m unittest discover -s tests -v
```

Generated files:

| Path | Contents |
| :--- | :--- |
| `reports/latest_report.md` | Latest report |
| `reports/report_*.md` | Archived reports; filenames use Asia/Shanghai time |
| `data/*_current.json` | Current observations and metric definitions |
| `data/source_status.json` | Source and category collection status |
| `data/history.json` | Last successful snapshots for the next comparison |
| `data/backups/` | History before each update |

On the first upgraded run, legacy history is preserved and new comparison baselines are established. Incorrect legacy ranks and ambiguous units are not carried into the new comparisons.

## Configure APIs and notifications

Copy `.env.example` to `.env` and fill in the settings you need. Keep keys in the local file or GitHub Secrets.

| Variable | Purpose |
| :--- | :--- |
| `OPENROUTER_API_KEY` | Optional; enables daily usage through the [OpenRouter Data API](https://openrouter.ai/docs/cookbook/administration/data-api) |
| `ARTIFICIAL_ANALYSIS_API_KEY` | Optional; enables intelligence, speed and Token prices through the [AA API](https://artificialanalysis.ai/api-reference) |
| `WXPUSHER_APP_TOKEN` | WxPusher application token |
| `WXPUSHER_UIDS` | Comma-separated recipient UIDs |
| `WXPUSHER_TOPIC_IDS` | Comma-separated topic IDs; configure UIDs, topics, or both |
| `SERVERCHAN_SENDKEY` | ServerChan notification key |

When an API key is configured, API failures are reported rather than silently switching to a different metric definition. Public HTML mode remains available without data API keys.

Sending a report requires an explicit flag:

```bash
python main.py --notify
```

## GitHub Actions

After forking, add the required settings under **Settings → Secrets and variables → Actions**, and enable repository content write access for the workflow. Run it manually from **Actions → Daily LLM Trend Report → Run workflow**.

The workflow runs regression tests before collection and notification. Missing sources, missing categories, or errors from configured notification channels produce a failing run. Generated reports and successful observations are still saved; raw collection files are retained as Actions artifacts for 30 days.

Local commands follow the same exit rules. Use `--allow-partial` only when incomplete sources are acceptable. This option does not suppress notification failures.

## Attribution

Reports link to the original sources. Arena data and OpenRouter Data API data follow their respective CC BY 4.0 attribution requirements. Retain attribution to Artificial Analysis when using its data. Refer to each source for data definitions, licensing terms and evaluation methods.
