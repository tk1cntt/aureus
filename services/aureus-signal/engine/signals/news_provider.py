import os
import json
import logging
import requests
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class NewsProvider:
    """
    Fetches economic calendar from Faireconomy JSON.
    Converts and caches results in GMT+7.
    """
    URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    CACHE_PATH = os.path.join(os.path.dirname(__file__), "../../../brain/news_calendar.json")
    _last_attempt = 0
    _cooldown = 300 # 5 minutes cooldown on failure

    @classmethod
    def fetch_this_week(cls, force: bool = False) -> list:
        """Fetch and process the calendar, saving to cache with age check and retries."""
        # 1. Age check
        if not force and os.path.exists(cls.CACHE_PATH):
            try:
                mtime = os.path.getmtime(cls.CACHE_PATH)
                if time.time() - mtime < 21600: # 6 hours
                    logger.info("📅 News calendar is fresh. Skipping fetch.")
                    return cls.get_cached()
            except Exception as e:
                logger.warning(f"Error checking cache age: {e}")

        # 2. Cooldown check
        if time.time() - cls._last_attempt < cls._cooldown:
            logger.debug("📅 News fetch cooling down. Using cache.")
            return cls.get_cached()

        cls._last_attempt = time.time()

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.forexfactory.com/"
        }

        retries = 2
        for attempt in range(retries + 1):
            try:
                logger.info(f"📡 Fetching Economic Calendar from FairEconomy (Attempt {attempt+1}/{retries+1})...")
                response = requests.get(cls.URL, headers=headers, timeout=25)
                response.raise_for_status()
                data = response.json()
                
                processed = cls._process_events(data)
                
                # Save to cache
                os.makedirs(os.path.dirname(cls.CACHE_PATH), exist_ok=True)
                with open(cls.CACHE_PATH, 'w', encoding='utf-8') as f:
                    json.dump(processed, f, indent=2)
                
                logger.info(f"✅ News calendar successfully fetched and cached ({len(processed)} events).")
                return processed
            except Exception as e:
                if attempt < retries:
                    wait_time = (attempt + 1) * 5
                    logger.warning(f"⚠️ Fetch attempt {attempt+1} failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ All {retries+1} attempts to fetch news failed: {e}")
        
        return cls.get_cached()

    @classmethod
    def get_cached(cls) -> list:
        """Retrieve events from local cache."""
        if os.path.exists(cls.CACHE_PATH):
            try:
                with open(cls.CACHE_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    @classmethod
    def _process_events(cls, raw_data: list) -> list:
        """
        Converts timezone to GMT+7 and filters for High Impact or Holiday.
        Original format is ISO but with -05:00 offset (EST).
        """
        processed = []
        for event in raw_data:
            impact = event.get('impact', 'Low')
            if impact not in ("High", "Holiday", "Medium"): # Keep Medium for awareness
                continue
                
            # Date Parsing: "2026-02-27T08:30:00-05:00"
            date_str = event.get('date')
            if not date_str:
                continue
                
            try:
                # Parse with timezone awareness
                dt_obj = datetime.fromisoformat(date_str)
                # Convert to GMT+7 (Asia/Ho_Chi_Minh)
                gmt7_tz = timezone(timedelta(hours=7))
                dt_gmt7 = dt_obj.astimezone(gmt7_tz)
                
                processed.append({
                    "title": event.get('title'),
                    "country": event.get('country'),
                    "impact": impact,
                    "date_gmt7": dt_gmt7.strftime("%Y-%m-%d %H:%M:%S"),
                    "timestamp": int(dt_gmt7.timestamp())
                })
            except Exception as e:
                logger.warning(f"Error parsing date {date_str}: {e}")
                
        # Sort by timestamp
        processed.sort(key=lambda x: x['timestamp'])
        return processed

    @classmethod
    def get_todays_events(cls, current_time_gmt7: datetime) -> list:
        """Filter cached events for the specific day."""
        events = cls.get_cached()
        if not events:
            events = cls.fetch_this_week() # Try fetch if empty
            
        today_str = current_time_gmt7.strftime("%Y-%m-%d")
        return [e for e in events if e['date_gmt7'].startswith(today_str)]
