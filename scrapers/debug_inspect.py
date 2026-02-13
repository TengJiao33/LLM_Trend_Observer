import asyncio
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        print("Navigating to OpenRouter Rankings...")
        await page.goto("https://openrouter.ai/rankings", wait_until="networkidle")
        await asyncio.sleep(15) # Wait for all JS to fire
        
        # Scroll to ensure everything is rendered
        await page.mouse.wheel(0, 1000)
        await asyncio.sleep(5)
        
        # Find all divs and check their content
        divs = await page.locator("div").all()
        print(f"Total Divs: {len(divs)}")
        
        potential_data = []
        for d in divs:
            try:
                text = await d.inner_text()
                if "/" in text and len(text) < 100: # Typical model id length
                    potential_data.append(text.strip())
            except:
                continue
        
        print(f"Found {len(potential_data)} potential model markers.")
        for item in list(set(potential_data))[:20]:
            print(f"  - {item}")
            
        content = await page.content()
        with open("rendered_inspect.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("Full rendered HTML saved to rendered_inspect.html")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
