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
            print("Extracting leaderboards with production-grade naming...")
            await asyncio.sleep(5)
            
            categories_data = {}
            tables = await current_frame.locator("table").all()
            print(f"Found {len(tables)} tables.")

            # 用户要求的标准命名映射
            # 顺序即优先级：匹配到即停止
            STANDARD_MAP = {
                "Code": ["code", "coding", "program"],
                "Vision": ["vision", "multi-modal", "multimodal"],
                "Text-to-Image": ["text-to-image", "t2i", "image gen"],
                "Image Edit": ["image edit", "edit"],
                "Search": ["search", "grounding", "web"],
                "Text-to-Video": ["text-to-video", "t2v", "video gen"],
                "Image-to-Video": ["image-to-video", "i2v"],
                "Text": ["text", "overall", "chat", "arena"]
            }

            for i, table in enumerate(tables):
                try:
                    headers = await table.locator("th").all_inner_texts()
                    if not headers or not any(h for h in headers if "Rank" in h or "Model" in h):
                        continue
                    
                    category_name = None
                    # 1. 精准提取
                    try:
                        curr = table
                        for _ in range(6): 
                            curr = curr.locator("xpath=..")
                            if await curr.count() == 0: break
                            texts = await curr.locator("span, p, div, h1, h2, h3, h4, .gr-label").all_inner_texts()
                            for t in texts:
                                t_clean = t.strip().lower()
                                if not t_clean or len(t_clean) > 30: continue
                                for std, kws in STANDARD_MAP.items():
                                    if any(kw in t_clean for kw in kws):
                                        category_name = std
                                        break
                                if category_name: break
                            if category_name: break
                    except:
                        pass

                    # 2. 数据提取
                    rows = await table.locator("tr").all()
                    temp_leaderboard = []
                    model_texts = []
                    for row in rows:
                        if not await row.is_visible(): continue
                        cells = await row.locator("td").all_inner_texts()
                        if cells and cells[0].isdigit():
                            m_raw = cells[1].strip()
                            model_texts.append(m_raw.lower())
                            temp_leaderboard.append({
                                "rank": int(cells[0]),
                                "model_id": m_raw,
                                "score": cells[2] if len(cells) > 2 else "-",
                                "votes": cells[3] if len(cells) > 3 else "-",
                                "timestamp": datetime.now().isoformat()
                            })
                    
                    if not temp_leaderboard: continue

                    # 3. 语义特征增强识别（Vision 兜底）
                    if not category_name or category_name == "Text":
                        all_models_str = " ".join(model_texts)
                        # 强特征识别
                        if any(x in all_models_str for x in ["flux", "sdxl", "stable-diffusion"]):
                            category_name = "Text-to-Image"
                        elif any(x in all_models_str for x in ["veo", "sora", "vidu"]):
                            category_name = "Text-to-Video"
                        elif any(x in all_models_str for x in ["code", "deepseek-coder", "codestral"]):
                            category_name = "Code"
                        elif i == 2: # 经验法则：第三个通常是 Vision
                            category_name = "Vision"
                        elif not category_name:
                            category_name = "Text"

                    # 4. 防止冲突
                    name = category_name
                    s = 1
                    while name in categories_data:
                        s += 1
                        name = f"{category_name}_{s}"

                    print(f"Assigning Table {i} to Category: {name}")
                    categories_data[name] = temp_leaderboard

                except Exception as e:
                    print(f"Error at table {i}: {e}")

            if categories_data:
                processed_data = {}
                for cat, data in categories_data.items():
                    # 去重
                    seen = set()
                    final = []
                    for d in sorted(data, key=lambda x: x["rank"]):
                        if d["model_id"] not in seen:
                            final.append(d)
                            seen.add(d["model_id"])
                    
                    # 命名清洗：移除不必要的数字后缀（除非确实是并列同赛道）
                    # 比如只有一个 Text 赛道时，不要叫 Text_1
                    processed_data[cat] = final

                os.makedirs("data", exist_ok=True)
                with open("data/lmsys_current.json", "w", encoding="utf-8") as f:
                    json.dump(processed_data, f, indent=4, ensure_ascii=False)
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


