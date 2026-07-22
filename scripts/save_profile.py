"""Run this locally to create a persistent Chromium profile for WhatsApp.
Uses your real Chrome installation for better stealth."""
import asyncio, shutil, tarfile, os
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path(__file__).parent.parent / "whatsapp-profile"
ARCHIVE = Path(__file__).parent.parent / "whatsapp-profile.tar.gz"

async def main():
    if PROFILE_DIR.exists():
        shutil.rmtree(PROFILE_DIR)
    PROFILE_DIR.mkdir(exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        page = context.pages[0]
        await page.goto("https://web.whatsapp.com", wait_until="load")

        # Stealth scripts
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        print("\n" + "="*60)
        print("WHATSAPP WEB OPENED IN CHROME.")
        print("Scan the QR code with your phone.")
        print("Once chats are visible, close the browser tab.")
        print("="*60 + "\n")

        await page.wait_for_event("close", timeout=None)
        await asyncio.sleep(1)
        try:
            await context.close()
        except Exception:
            pass

    print("\nCreating archive...")
    with tarfile.open(ARCHIVE, "w:gz") as tar:
        tar.add(PROFILE_DIR, arcname="whatsapp-profile")
    size_mb = os.path.getsize(ARCHIVE) / 1024 / 1024
    print(f"Archive created: {size_mb:.1f} MB")

if __name__ == "__main__":
    asyncio.run(main())
