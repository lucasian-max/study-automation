import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def main():
    config = json.load(open("config.json"))
    wp = config["whatsapp"]
    session_dir = Path(wp["session_dir"])
    session_dir.mkdir(exist_ok=True)
    state_file = session_dir / "state.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("Opening WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")
        await page.wait_for_load_state("domcontentloaded")

        print("\n⚠️  Scan the QR code with your phone.")
        print("Then come back to this terminal and press ENTER.\n")
        input("Press ENTER after scanning...")

        await context.storage_state(path=str(state_file))
        print(f"\n✅ Session saved to {state_file}")
        print("WhatsApp setup complete! You can now run the main script.\n")
        await browser.close()


asyncio.run(main())
