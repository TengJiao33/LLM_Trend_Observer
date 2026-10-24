"""Collect, validate, compare and optionally publish a daily report."""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from compare import DeltaEngine
from scrapers.artalanaly_scraper import scrape_artalanaly
from scrapers.lmsys_scraper import CONFIGS, scrape_lmsys_hf
from scrapers.openrouter_scraper import scrape_openrouter
from utils.data import snapshot, utc_now, validate_board, write_json

COLLECTORS = {"openrouter": scrape_openrouter, "lmsys": scrape_lmsys_hf, "artalanaly": scrape_artalanaly}
SOURCE_LABELS = {"openrouter": "OpenRouter", "lmsys": "Arena", "artalanaly": "Artificial Analysis"}


def collect_sources(data_dir):
    current, statuses = {}, {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        tasks = {executor.submit(collector): source for source, collector in COLLECTORS.items()}
        for future in as_completed(tasks):
            source = tasks[future]
            try:
                result = future.result()
                if not result.get("boards"):
                    raise ValueError("No leaderboard data returned")
                for name in list(result["boards"]):
                    try:
                        board = result["boards"][name]
                        validate_board(board)
                        board["fetched_at"] = result["fetched_at"]
                        board["method"] = result["method"]
                    except (ValueError, TypeError, KeyError) as exc:
                        result.setdefault("errors", {})[name] = str(exc)
                        del result["boards"][name]
                if source == "lmsys":
                    for name in CONFIGS:
                        if name not in result["boards"]:
                            result["errors"].setdefault(name, "Category unavailable")
            except Exception as exc:
                result = snapshot(source, "", "unavailable", {}, errors={"source": str(exc)})
            state = "ok" if result["boards"] and not result["errors"] else "partial" if result["boards"] else "failed"
            current[source] = result
            statuses[source] = {"state": state, "fetched_at": result["fetched_at"],
                                "boards": len(result["boards"]), "errors": result["errors"]}
            write_json(Path(data_dir) / f"{source}_current.json", result)
            print(f"{SOURCE_LABELS[source]}: {state} ({len(result['boards'])} leaderboards)")
    write_json(Path(data_dir) / "source_status.json", statuses)
    return current, statuses


def run_pipeline(data_dir="data", output_dir="reports", notify=False, allow_partial=False):
    from report_generator import ReportGenerator

    current, statuses = collect_sources(data_dir)
    engine = DeltaEngine(Path(data_dir) / "history.json")
    generator = ReportGenerator(output_dir, engine)
    report_path = generator.generate(current, statuses)
    engine.update_many(current)
    degraded = any(s["state"] != "ok" for s in statuses.values())
    notified = True
    if notify:
        from utils.notifier import HubNotifier

        title = "LLM Trend Observer | " + generator.report_date
        notified = HubNotifier().send_all(Path(report_path).read_text(encoding="utf-8"), title)
        print("Notification accepted by configured channels." if notified else "Notification failed or no channels configured.")
    print(f"Report: {report_path}")
    return 1 if (degraded and not allow_partial) or not notified else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data", help="Snapshot and history directory")
    parser.add_argument("--output-dir", default="reports", help="Markdown report directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--notify", action="store_true", help="Send to configured notification channels")
    mode.add_argument("--no-notify", action="store_true", help="Generate a report without sending (default)")
    parser.add_argument("--allow-partial", action="store_true", help="Allow degraded data sources without a failing exit status")
    args = parser.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    return run_pipeline(args.data_dir, args.output_dir, args.notify, args.allow_partial)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
