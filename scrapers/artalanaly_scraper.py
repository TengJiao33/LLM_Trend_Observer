import asyncio
import json
import os
from playwright.async_api import async_playwright
from datetime import datetime

async def scrape_artalanaly():
    print("Starting Artificial Analysis Scrape (Embed Leaderboard)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            url = "https://artificialanalysis.ai/embed/llm-performance-leaderboard"
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Artificial Analysis usually loads a large table. 
            # We need to wait for it.
            await asyncio.sleep(5)
            
            # The embedded page typically has a table with columns like:
            # Model, Quality Index, Speed/Throughput, Price
            
            results = {
                "Intelligence": [],
                "Speed": [],
                "Price": []
            }
            
            # Try to identify columns
            headers = await page.locator("th").all_inner_texts()
            print(f"Found headers: {headers}")
            
            col_map = {}
            for i, h in enumerate(headers):
                h_clean = h.lower()
                if "model" in h_clean: col_map["model"] = i
                if "quality" in h_clean or "intelligence" in h_clean or "index" in h_clean: 
                    col_map["intelligence"] = i
                if "tokens/sec" in h_clean or "speed" in h_clean or "throughput" in h_clean:
                    col_map["speed"] = i
                if "price" in h_clean or "cost" in h_clean:
                    col_map["price"] = i
            
            print(f"Detected column mapping: {col_map}")
            
            # Diagnostic: Save HTML and Screenshot
            await page.screenshot(path="artalanaly_debug.png")
            content = await page.content()
            with open("artalanaly_debug.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("Debug screenshot and HTML saved.")

            rows = await page.locator("tr").all()
            all_data = []
            
            print(f"Found {len(rows)} rows total.")
            for i, row in enumerate(rows):
                cells = await row.locator("td, th").all_inner_texts()
                if not cells or len(cells) < 7: continue
                
                # Check if it's a header-like row (skip rows like Row 0 and Row 1 from dump)
                if "Model" in cells[1] or "API" in cells[0]:
                    continue

                provider = cells[0].strip()
                model_name = cells[1].strip()
                # Construct ID: Model (Provider)
                full_id = f"{model_name} ({provider})"
                
                def parse_val(val):
                    v = val.strip().replace("$", "").replace("%", "").replace("/M", "").replace(",", "")
                    if "k" in v.lower():
                        v = float(v.lower().replace("k", "")) * 1000
                    elif "m" in v.lower():
                        v = float(v.lower().replace("m", "")) * 1000000
                    try:
                        return float(v)
                    except:
                        return None

                intel_val = parse_val(cells[4])
                price_val = parse_val(cells[5])
                speed_val = parse_val(cells[6])

                all_data.append({
                    "model_id": full_id,
                    "model_base": model_name,
                    "intelligence_raw": cells[4].strip(),
                    "intelligence": intel_val,
                    "price_raw": cells[5].strip(),
                    "price": price_val,
                    "speed_raw": cells[6].strip(),
                    "speed": speed_val,
                    "timestamp": datetime.now().isoformat()
                })
            
            if not all_data:
                print("No data extracted from table rows.")
                return False

            # --- Deduplicate and Sort ---
            
            # 1. Intelligence (Descending)
            intel_list = sorted(
                [d for d in all_data if d["intelligence"] is not None],
                key=lambda x: x["intelligence"],
                reverse=True
            )
            seen = set()
            for item in intel_list:
                if item["model_base"] not in seen:
                    results["Intelligence"].append({
                        "rank": len(results["Intelligence"]) + 1,
                        "model_id": item["model_id"],
                        "score": item["intelligence_raw"]
                    })
                    seen.add(item["model_base"])
                if len(results["Intelligence"]) >= 10: break

            # 2. Speed (Descending)
            speed_list = sorted(
                [d for d in all_data if d["speed"] is not None],
                key=lambda x: x["speed"],
                reverse=True
            )
            seen = set()
            for item in speed_list:
                if item["model_base"] not in seen:
                    results["Speed"].append({
                        "rank": len(results["Speed"]) + 1,
                        "model_id": item["model_id"],
                        "score": item["speed_raw"]
                    })
                    seen.add(item["model_base"])
                if len(results["Speed"]) >= 10: break

            # 3. Price (Ascending, ignore $0.00)
            price_list = sorted(
                [d for d in all_data if d["price"] is not None and d["price"] > 0],
                key=lambda x: x["price"]
            )
            seen = set()
            for item in price_list:
                if item["model_base"] not in seen:
                    results["Price"].append({
                        "rank": len(results["Price"]) + 1,
                        "model_id": item["model_id"],
                        "score": item["price_raw"]
                    })
                    seen.add(item["model_base"])
                if len(results["Price"]) >= 10: break

            if any(results.values()):
                os.makedirs("data", exist_ok=True)
                with open("data/artalanaly_current.json", "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=4, ensure_ascii=False)
                print("Success: Artificial Analysis data saved with correct indexing.")
                return True
            else:
                print("Warning: No data extracted from Artificial Analysis.")
                await page.screenshot(path="artalanaly_error.png")
                return False
                
        except Exception as e:
            print(f"Error during ArtalAnaly scrape: {e}")
            return False
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_artalanaly())
