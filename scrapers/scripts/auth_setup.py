import argparse
import asyncio
import logging

from scrapers.core.browser_engine import BrowserManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_auth(source: str):
    logger.info(f"Setting up authentication for source: {source}")
    
    # We set headless=False so the user can interactively solve captchas and log in
    manager = BrowserManager(headless=False, timeout=600)
    await manager.start()
    
    # Use a fixed session ID for the source to reuse later in background workers
    session_id = f"{source}_auth_session"
    session = await manager.acquire(session_id)
    
    try:
        logger.info(f"Browser opened. Please log in to {source} manually within the next 5 minutes.")
        if source == "upwork":
            await session.page.goto("https://www.upwork.com/ab/account-security/login")
        elif source == "linkedin":
            await session.page.goto("https://www.linkedin.com/login")
        else:
            logger.warning(f"Unknown source '{source}'. Navigating to google.com as fallback.")
            await session.page.goto("https://www.google.com")
            
        # Keep browser open for 5 minutes (300 seconds) to allow manual login
        await asyncio.sleep(300)
        logger.info("Time is up. Saving session cookies and closing browser.")
    finally:
        await manager.release(session)
        await manager.stop()
        logger.info(f"Auth session '{session_id}' saved successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manual authentication setup for scrapers")
    parser.add_argument("--source", choices=["upwork", "linkedin"], required=True, help="The source to authenticate")
    args = parser.parse_args()
    
    asyncio.run(setup_auth(args.source))
