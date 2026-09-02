import asyncio
import os
import logging
from datetime import datetime
from typing import List, Tuple
from playwright.async_api import async_playwright, Page, BrowserContext, Error as PlaywrightError

from .models import Tweet
from .exceptions import XSessionState, XTimeoutError, XNetworkError, XParseError
from .parser import parse_tweet_element

import json
from dotenv import load_dotenv

STATE_FILE = os.path.join("data", "x", "playwright_state.json")
DEBUG_DIR = os.path.join("data", "x", "debug")

MAX_SCROLLS = 10
MAX_TWEETS = 50
MAX_DURATION = 45  # seconds

def _sync_cookies_from_env():
    load_dotenv()
    cookie_str = os.getenv("X_COOKIES", "")
    if not cookie_str or "auth_token=" not in cookie_str:
        return False
        
    cookies = []
    future_expiry = 2102971848 # Year 2036
    
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            for domain in [".x.com", ".twitter.com"]:
                cookies.append({
                    "name": k,
                    "value": v,
                    "domain": domain,
                    "path": "/",
                    "expires": future_expiry,
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax"
                })
                
    state = {"cookies": cookies, "origins": []}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return True

async def _save_debug_snapshot(page: Page, username: str):
    os.makedirs(DEBUG_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(DEBUG_DIR, f"{username}_failed_{stamp}.html")
    png_path = os.path.join(DEBUG_DIR, f"{username}_failed_{stamp}.png")
    try:
        content = await page.content()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        await page.screenshot(path=png_path)
        logging.info(f"Debug snapshot saved: {html_path}")
    except Exception as e:
        logging.warning(f"Failed to save debug snapshot: {e}")

async def validate_session(page: Page) -> XSessionState:
    """Checks if the current page requires login."""
    url = page.url
    if "login" in url or "i/flow/login" in url:
        return XSessionState.LOGIN_REQUIRED
    
    # Check for specific challenge pages
    if "challenge" in url or "locked" in url:
        return XSessionState.CHALLENGE
        
    return XSessionState.VALID

async def scrape_profile(username: str, last_seen_tweet_id: str = None) -> Tuple[XSessionState, List[Tweet]]:
    """
    Navigates to a user's profile and extracts tweets incrementally.
    Returns (SessionState, List[Tweet]).
    """
    # Always attempt to sync the latest cookies from .env directly
    if not _sync_cookies_from_env():
        if not os.path.exists(STATE_FILE):
            return XSessionState.LOGIN_REQUIRED, []

    tweets_collected = []
    seen_ids = set()
    start_time = datetime.now()
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                storage_state=STATE_FILE,
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            try:
                # Use domcontentloaded to avoid waiting forever for X's websockets
                await page.goto(f"https://x.com/{username}", wait_until="domcontentloaded", timeout=20000)
            except PlaywrightError as e:
                if "Timeout" in str(e):
                    await browser.close()
                    raise XTimeoutError(f"Timeout navigating to @{username}")
                raise XNetworkError(f"Network error navigating to @{username}: {e}")

            # Check for Retry button (Twitter often rate limits fast page loads)
            try:
                retry_btn = page.locator('div[role="button"]:has-text("Retry")')
                if await retry_btn.count() > 0:
                    await retry_btn.first.click()
                    await page.wait_for_timeout(3000)
            except Exception:
                pass
                
            # Wait for at least one tweet to actually render (increased to 30 seconds for heavy accounts)
            try:
                await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
            except PlaywrightError:
                state = await validate_session(page)
                if state != XSessionState.VALID:
                    await browser.close()
                    return state, []
                
                # If valid but no articles, might be an empty profile or block
                await _save_debug_snapshot(page, username)
                await browser.close()
                raise XParseError(f"Could not find timeline for @{username}")

            state = await validate_session(page)
            if state != XSessionState.VALID:
                await browser.close()
                return state, []

            # Scraping Loop
            scrolls = 0

            
            while scrolls < MAX_SCROLLS and len(tweets_collected) < MAX_TWEETS:
                if (datetime.now() - start_time).total_seconds() > MAX_DURATION:
                    logging.info(f"Scraper reached max duration for @{username}.")
                    break
                    
                articles = page.locator('article[data-testid="tweet"]')
                count = await articles.count()
                
                new_tweets_in_scroll = False
                
                for i in range(count):
                    tweet = await parse_tweet_element(articles.nth(i), username)
                    if not tweet or tweet.id in seen_ids:
                        continue
                        
                    seen_ids.add(tweet.id)
                    tweets_collected.append(tweet)
                    new_tweets_in_scroll = True
                    
                    if len(tweets_collected) >= MAX_TWEETS:
                        break
                if not new_tweets_in_scroll:
                    # Scroll down
                    await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)
                
                scrolls += 1
                
            if len(tweets_collected) == 0:
                await _save_debug_snapshot(page, f"{username}_0_tweets")
                logging.warning(f"X: Collected 0 tweets. Saved debug snapshot for @{username}")
                
            await browser.close()
            return XSessionState.VALID, tweets_collected
            
    except XTimeoutError:
        raise
    except XNetworkError:
        raise
    except XParseError:
        raise
    except Exception as e:
        raise XScraperError(f"Unexpected Playwright error: {e}")
