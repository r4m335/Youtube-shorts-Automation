from typing import Optional
from datetime import datetime
from .models import Tweet

async def parse_tweet_element(article_locator, username: str) -> Optional[Tweet]:
    """
    Parses a single Playwright Locator representing an <article> node.
    Extracts multiple heuristic signals to build a Tweet object.
    """
    try:
        # 1. URL and ID
        # Look for the timestamp link which usually contains /username/status/ID
        time_link = article_locator.locator('a[href*="/status/"]:has(time)').first
        url = await time_link.get_attribute('href') if await time_link.count() > 0 else None
        
        if not url:
            # Fallback: find any link matching the pattern
            status_links = article_locator.locator(f'a[href*="/status/"]')
            count = await status_links.count()
            for i in range(count):
                href = await status_links.nth(i).get_attribute('href')
                if href and '/status/' in href and 'analytics' not in href:
                    url = href
                    break
        
        if not url:
            return None # Cannot identify tweet without ID/URL
            
        tweet_id = url.split('/status/')[1].split('/')[0].split('?')[0]
        full_url = f"https://x.com{url}" if url.startswith('/') else url

        # 2. Timestamp
        time_elem = article_locator.locator('time').first
        created_at = None
        if await time_elem.count() > 0:
            dt_str = await time_elem.get_attribute('datetime')
            if dt_str:
                try:
                    # Remove 'Z' and parse
                    created_at = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                except ValueError:
                    pass

        # 3. Text content
        text_elem = article_locator.locator('[data-testid="tweetText"]').first
        if await text_elem.count() > 0:
            text = await text_elem.inner_text()
        else:
            # Fallback: grab all text in the article and strip known metadata
            # This is brittle but better than nothing
            text = await article_locator.inner_text()
            
        # 4. Metrics (using aria-labels from action buttons)
        reply_count, repost_count, like_count, view_count = 0, 0, 0, 0
        
        reply_btn = article_locator.locator('[data-testid="reply"]').first
        if await reply_btn.count() > 0:
            aria = await reply_btn.get_attribute('aria-label') or ""
            reply_count = _parse_metric(aria)
            
        repost_btn = article_locator.locator('[data-testid="retweet"]').first
        if await repost_btn.count() > 0:
            aria = await repost_btn.get_attribute('aria-label') or ""
            repost_count = _parse_metric(aria)
            
        like_btn = article_locator.locator('[data-testid="like"]').first
        if await like_btn.count() > 0:
            aria = await like_btn.get_attribute('aria-label') or ""
            like_count = _parse_metric(aria)

        is_repost = False
        # X identifies reposts usually with a specific text indicator at the top
        # We can check if the author of the status URL matches the scraped username
        if username.lower() not in url.lower():
            is_repost = True

        # 5. Media (Images/Video thumbnails)
        media_urls = []
        imgs = article_locator.locator('img')
        img_count = await imgs.count()
        for i in range(img_count):
            src = await imgs.nth(i).get_attribute('src')
            # Only grab actual tweet media, not profile pictures, emojis, or badges
            if src and "pbs.twimg.com/media/" in src:
                # Convert thumbnail to high-res (change name=small to name=large)
                large_src = src.replace('name=small', 'name=large').replace('name=240x240', 'name=large')
                if large_src not in media_urls:
                    media_urls.append(large_src)

        return Tweet(
            id=tweet_id,
            username=username,
            text=text,
            url=full_url,
            created_at=created_at,
            reply_count=reply_count,
            repost_count=repost_count,
            like_count=like_count,
            view_count=view_count,
            is_repost=is_repost,
            media=media_urls
        )
    except Exception:
        return None

def _parse_metric(aria_label: str) -> int:
    # E.g. "123 replies" -> 123
    # "4.5K likes" -> 4500
    try:
        parts = aria_label.split()
        if not parts:
            return 0
        num_str = parts[0].replace(',', '')
        multiplier = 1
        if num_str.upper().endswith('K'):
            multiplier = 1000
            num_str = num_str[:-1]
        elif num_str.upper().endswith('M'):
            multiplier = 1000000
            num_str = num_str[:-1]
            
        return int(float(num_str) * multiplier)
    except Exception:
        return 0
