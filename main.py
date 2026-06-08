import asyncio
import json
import os
from datetime import datetime

from compare import DeltaEngine
from scrapers.artalanaly_scraper import scrape_artalanaly
from scrapers.hf_leaderboard_scraper import scrape_hf_leaderboard
from scrapers.lmsys_scraper import scrape_lmsys_hf
from scrapers.openrouter_scraper import scrape_openrouter


SOURCES = [
    ("openrouter", "OpenRouter", "data/openrouter_current.json"),
    ("lmsys", "LMSYS/Arena", "data/lmsys_current.json"),
    ("artalanaly", "Artificial Analysis", "data/artalanaly_current.json"),
    ("hf_leaderboard", "Hugging Face Leaderboard", "data/hf_leaderboard_current.json"),
]
STATUS_FILE = "data/source_status.json"


def _load_json(file_path):
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _clear_current_files():
    for _, _, file_path in SOURCES:
        if os.path.exists(file_path):
            os.remove(file_path)


def _write_source_status(statuses):
    os.makedirs("data", exist_ok=True)
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(statuses, f, indent=4, ensure_ascii=False)


async def _run_scrapers():
    scraper_tasks = {
        "openrouter": scrape_openrouter(),
        "lmsys": scrape_lmsys_hf(),
        "artalanaly": scrape_artalanaly(),
        "hf_leaderboard": asyncio.to_thread(scrape_hf_leaderboard),
    }
    file_paths = {source_name: file_path for source_name, _, file_path in SOURCES}

    results = await asyncio.gather(*scraper_tasks.values(), return_exceptions=True)
    statuses = {}

    for source_name, result in zip(scraper_tasks.keys(), results):
        error = None
        if isinstance(result, Exception):
            success = False
            error = repr(result)
        else:
            success = bool(result)

        statuses[source_name] = {
            "success": success,
            "file": file_paths[source_name],
            "has_current": os.path.exists(file_paths[source_name]),
            "error": error,
            "timestamp": datetime.now().isoformat(),
        }

    return statuses


def _collect_history_updates(sources, statuses):
    updates = {}

    for source_name, _, file_path in sources:
        if not statuses.get(source_name, {}).get("success"):
            continue
        if not os.path.exists(file_path):
            continue

        curr_data = _load_json(file_path)
        if isinstance(curr_data, dict):
            for cat, data in curr_data.items():
                updates[f"{source_name}_{cat}"] = data
        else:
            updates[source_name] = curr_data

    return updates


async def run_pipeline():
    print("=== LLM Trend Observer Pipeline Start ===")
    os.makedirs("data", exist_ok=True)

    # 1. Scraping
    print("\n[1/4] Running Scrapers...")
    _clear_current_files()
    statuses = await _run_scrapers()
    _write_source_status(statuses)

    for source_name, display_name, _ in SOURCES:
        status = statuses[source_name]
        if status["success"]:
            print(f"Success: {display_name} scraping completed.")
        else:
            print(f"Warning: {display_name} scraping failed.")
            if status["error"]:
                print(f"  Error: {status['error']}")

    # 2. Comparison
    print("\n[2/4] Generating Delta Reports...")
    engine = DeltaEngine()

    for source_name, _, file_path in SOURCES:
        if os.path.exists(file_path):
            curr_data = _load_json(file_path)

            if isinstance(curr_data, dict):
                print(f"\n[2/4] Processing Multi-Category source: {source_name}")
                for cat, data in curr_data.items():
                    full_key = f"{source_name}_{cat}"
                    report = engine.compare(full_key, data)

                    print(f"\n--- {full_key.upper()} Delta Report ---")
                    for r in report[:5]:
                        print(f"Rank {r['rank']}: {r['model_id']} ({r['delta']})")
            else:
                report = engine.compare(source_name, curr_data)

                print(f"\n--- {source_name.upper()} Delta Report ---")
                for r in report[:10]:
                    print(f"Rank {r['rank']}: {r['model_id']} ({r['delta']})")
        else:
            print(f"Skipping {source_name}: Data file not found.")

    # 3. Report Generation
    print("\n[3/4] Generating Markdown Report...")
    from report_generator import ReportGenerator

    generator = ReportGenerator()
    report_path = generator.generate()
    print(f"Technician Report created at: {report_path}")

    print("\n[3.5/4] Updating History...")
    updates = _collect_history_updates(SOURCES, statuses)
    engine.update_many(updates)
    print(f"History updated for {len(updates)} source/category entries.")

    # 4. Notification
    print("\n[4/4] Notification System...")
    if os.path.exists(report_path):
        from utils.notifier import HubNotifier

        notifier = HubNotifier()
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()

        report_title = f"🔭 大模型今日趋势 {datetime.now().strftime('%m-%d')}"
        success = notifier.send_all(report_content, report_title)
        if success:
            print("Notification triggered successfully.")
        else:
            print("Notification failed or skipped (Check credentials).")
    else:
        print("No report file found to notify.")

    print("\n=== Pipeline Completed ===")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
