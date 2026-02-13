import json
import os
import re
from playwright.async_api import async_playwright
from datetime import datetime
import asyncio

async def scrape_openrouter():
    print("Starting OpenRouter Scrape via Structured Text (This Week)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_viewport_size({"width": 1280, "height": 3000})
            await page.goto("https://openrouter.ai/rankings", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(15)
            
            body_text = await page.evaluate("document.body.innerText")
            
            models = []
            seen = set()
            
            # Based on body_debug.txt info:
            # Pattern: (\d+)\.\n([^\n]+)\nby\n([^\n]+)\n([^\n]+ tokens)\n([^\n]+%)
            # We use a pattern that captures the rank, model, provider, tokens, and growth
            matches = re.finditer(r'(\d+)\.\s*\n?([^\n]+)\s*\n?by\s*\n?([^\n]+)\s*\n?([^\n]+ tokens)\s*\n?([^\n]+%)', body_text)
            
            for m in matches:
                rank = int(m.group(1))
                model_name = m.group(2).strip()
                provider = m.group(3).strip()
                tokens = m.group(4).strip()
                growth = m.group(5).strip()
                
                model_id = f"{provider}/{model_name}".lower().replace(" ", "-")
                
                if model_id not in seen:
                    models.append({
                        "rank": rank,
                        "model_id": model_id,
                        "display_name": model_name,
                        "provider": provider,
                        "tokens": tokens,
                        "growth": growth,
                        "timestamp": datetime.now().isoformat()
                    })
                    seen.add(model_id)
                if len(models) >= 30: break
            
            if models:
                os.makedirs("data", exist_ok=True)
                with open("data/openrouter_current.json", "w", encoding="utf-8") as f:
                    json.dump(models, f, indent=4, ensure_ascii=False)
                print(f"Success! Extracted {len(models)} structured model rankings.")
            else:
                print("No structured models found. Falling back to simple regex...")
                # (Keep the fallback logic from before just in case)
                
        except Exception as e:
            print(f"OpenRouter Structured Scrape Failed: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_openrouter())
