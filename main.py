import asyncio
import os
import json
from scrapers.openrouter_scraper import scrape_openrouter
from scrapers.lmsys_scraper import scrape_lmsys_hf
from compare import DeltaEngine

async def run_pipeline():
    print("=== LLM Trend Observer Pipeline Start ===")
    
    # 1. Scraping
    print("\n[1/3] Running Scrapers...")
    or_success = await scrape_openrouter()
    lmsys_success = await scrape_lmsys_hf()
    
    if not or_success:
        print("Warning: OpenRouter scraping failed.")
    if not lmsys_success:
        print("Warning: LMSYS scraping failed.")

    # 2. Comparison
    print("\n[2/3] Generating Delta Reports...")
    engine = DeltaEngine()
    
    sources = [
        ("openrouter", "data/openrouter_current.json"),
        ("lmsys", "data/lmsys_current.json")
    ]
    
    all_reports = {}
    
    for source_name, file_path in sources:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                curr_data = json.load(f)
                report = engine.compare(source_name, curr_data)
                all_reports[source_name] = report
                
                print(f"\n--- {source_name.upper()} Delta Report ---")
                for r in report[:10]:
                    status = r['delta']
                    print(f"Rank {r['rank']}: {r['model_id']} ({status})")
                
                # Update history after reporting
                engine.update_history(source_name, curr_data)
        else:
            print(f"Skipping {source_name}: Data file not found.")

    # 3. Report Generation
    print("\n[3/4] Generating Markdown Report...")
    from report_generator import ReportGenerator
    generator = ReportGenerator()
    report_path = generator.generate()
    print(f"Technician Report created at: {report_path}")

    # 4. Notification (P5)
    print("\n[4/4] Notification System...")
    if os.path.exists(report_path):
        from utils.notifier import HubNotifier
        notifier = HubNotifier()
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
        
        from datetime import datetime
        report_title = f"🤖 大模型今日趋势-{datetime.now().strftime('%m-%d')}"
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
