import asyncio
from browser_use import Browser, BrowserConfig
async def test():
    b = Browser(config=BrowserConfig(extra_chromium_args=["--user-data-dir=/tmp/foo_sandbox"]))
    ctx = await b.new_context()
    page = await ctx.get_current_page()
    await page.goto("https://example.com")
    print("DONE")
    await b.close()
asyncio.run(test())
