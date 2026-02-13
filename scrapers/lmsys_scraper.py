import asyncio
import json
import os
import re
from playwright.async_api import async_playwright
from datetime import datetime

import asyncio
import json
import os
import re
from playwright.async_api import async_playwright
from datetime import datetime

async def scrape_lmsys_hf():
    print("Starting LMSYS Scrape (Direct URL access)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Try direct URL first, then fall back to HF Space if needed
            url = "https://lmarena.ai/leaderboard"
            print(f"Navigating to {url}...")
            # Set longer timeout and wait for networkidle
            await page.goto(url, wait_until="networkidle", timeout=120000)
            
            # 1. Handle Nested Iframes (if any)
            # Sometimes even the direct URL might have internal frames
            current_frame = page
            
            # Check for Gradio/Leaderboard iframe
            try:
                # Wait for the table to appear, looking for GPT-4o which is usually there
                print("Waiting for 'GPT-4' record to appear as a signal...")
                await page.wait_for_selector("text=GPT-4", timeout=60000)
            except:
                print("Primary selector failed. Checking for iframes...")
                frames = page.frames
                for f in frames:
                    if "leaderboard" in f.url or "googleusercontent" in f.url:
                        current_frame = f
                        print(f"Switched to suspected frame: {f.url}")
                        break
            
            print("Extracitng rows...")
            # 2. Extract Data
            # Wait a bit more for the full list to render
            await asyncio.sleep(5)
            
            rows = await current_frame.locator("tr").all()
            print(f"Found {len(rows)} potential rows.")
            
            leaderboard = []
            for row in rows:
                try:
                    text = await row.inner_text()
                    # Clean the text: replace tabs with newlines, split by newlines
                    parts = [p.strip() for p in re.split(r'\t|\n', text) if p.strip()]
                    
                    # Log first few rows for debugging
                    if len(leaderboard) < 3:
                        print(f"Sample row parts: {parts}")

                    # LMSYS table structure check
                    # Rank, Model, Score, Votes
                    if parts and parts[0].isdigit():
                        rank = int(parts[0])
                        model_id = parts[1]
                        score = parts[2] if len(parts) > 2 else "-"
                        votes = parts[3] if len(parts) > 3 else "-"
                        
                        leaderboard.append({
                            "rank": rank,
                            "model_id": model_id,
                            "score": score,
                            "votes": votes,
                            "timestamp": datetime.now().isoformat()
                        })
                except:
                    continue
            
            if leaderboard:
                # Deduplicate and sort
                seen_models = set()
                unique_leaderboard = []
                for item in leaderboard:
                    if item["model_id"] not in seen_models:
                        unique_leaderboard.append(item)
                        seen_models.add(item["model_id"])
                
                unique_leaderboard.sort(key=lambda x: x["rank"])
                
                os.makedirs("data", exist_ok=True)
                with open("data/lmsys_current.json", "w", encoding="utf-8") as f:
                    json.dump(unique_leaderboard, f, indent=4, ensure_ascii=False)
                print(f"Successfully saved {len(unique_leaderboard)} models to data/lmsys_current.json")
                return True
            else:
                # If still failing, take a screenshot and save HTML for debugging
                await page.screenshot(path="lmsys_error_screenshot.png")
                content = await page.content()
                with open("lmsys_error_debug.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("Failed to extract data. Screenshot and HTML saved for debugging.")
                return False
                
        except Exception as e:
            print(f"Error during LMSYS scrape: {e}")
            return False
        finally:
            await browser.close()


