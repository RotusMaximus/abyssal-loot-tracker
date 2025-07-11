import sqlite3
import time
import httpx
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Optional

# --- Configuration ---
BASE_API_URL = "https://evetycoon.com/api"
REGION_ID = 10000002
SDE_DB_PATH = Path("./db/eve-sde-2025-07-07.sqlite")
PRICE_CACHE_DB_PATH = Path("./db/price_cache.sqlite")
CACHE_DURATION_SECONDS = 4 * 60 * 60  # 4 hours

# --- Database Management ---


def initialize_price_db():
    """Creates the price cache SQLite database and table if they don't exist."""
    PRICE_CACHE_DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(PRICE_CACHE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                type_id INTEGER PRIMARY KEY,
                min_sell REAL,
                max_buy REAL,
                last_updated INTEGER
            )
        """)
        conn.commit()


def get_type_id_from_sde(item_name: str) -> Optional[int]:
    """Queries the EVE SDE to find the typeID for a given item name."""
    if not SDE_DB_PATH.exists():
        print(f"Error: SDE database not found at {SDE_DB_PATH}")
        return None
    with sqlite3.connect(SDE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT typeID FROM invTypes WHERE typeName=?", (item_name,))
        result = cursor.fetchone()
        return result[0] if result else None

# --- Caching and API Logic ---


def get_cached_price(type_id: int) -> Optional[Tuple[float, float]]:
    """Retrieves a price from the cache if it's not expired."""
    with sqlite3.connect(PRICE_CACHE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT min_sell, max_buy, last_updated FROM prices WHERE type_id=?", (type_id,))
        result = cursor.fetchone()
        if result:
            min_sell, max_buy, last_updated = result
            if time.time() - last_updated < CACHE_DURATION_SECONDS:
                return min_sell, max_buy
    return None


def update_cached_price(type_id: int, min_sell: float, max_buy: float):
    """Updates or inserts a price into the cache."""
    with sqlite3.connect(PRICE_CACHE_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prices (type_id, min_sell, max_buy, last_updated)
            VALUES (?, ?, ?, ?)
        """, (type_id, min_sell, max_buy, int(time.time())))
        conn.commit()


async def fetch_price_from_api(session: httpx.AsyncClient, type_id: int) -> Optional[Tuple[float, float]]:
    """Fetches price data for a single typeID from the EveTycoon API."""
    url = f"{BASE_API_URL}/v1/market/stats/{REGION_ID}/{type_id}"
    try:
        response = await session.get(url, timeout=10.0)
        response.raise_for_status()  # Raises exception for 4xx/5xx responses
        data = response.json()
        min_sell = data.get("minSell", 0.0)
        max_buy = data.get("maxBuy", 0.0)
        return min_sell, max_buy
    except httpx.RequestError as e:
        print(f"API request failed for typeID {type_id}: {e}")
    except Exception as e:
        print(f"Failed to parse price data for typeID {type_id}: {e}")
    return None

# --- Main Public Function ---


async def get_prices_for_items(item_names: list[str]) -> Dict[str, Dict[str, float]]:
    """
    Efficiently gets prices for a list of item names, using cache and concurrent API calls.
    Returns a dictionary mapping item names to their price data.
    """
    price_results = {}
    items_to_fetch_api = {}

    # 1. Get typeIDs and check cache
    for name in item_names:
        type_id = get_type_id_from_sde(name)
        if not type_id:
            price_results[name] = {"min_sell": 0.0, "max_buy": 0.0}
            continue

        cached = get_cached_price(type_id)
        if cached:
            price_results[name] = {"min_sell": cached[0], "max_buy": cached[1]}
        else:
            items_to_fetch_api[name] = type_id

    # 2. Fetch missing prices from API concurrently
    if items_to_fetch_api:
        async with httpx.AsyncClient() as session:
            tasks = [fetch_price_from_api(session, type_id)
                     for type_id in items_to_fetch_api.values()]
            api_price_tuples = await asyncio.gather(*tasks)

            for item_name, type_id, price_tuple in zip(items_to_fetch_api.keys(), items_to_fetch_api.values(), api_price_tuples):
                if price_tuple:
                    min_sell, max_buy = price_tuple
                    price_results[item_name] = {
                        "min_sell": min_sell, "max_buy": max_buy}
                    update_cached_price(type_id, min_sell, max_buy)
                else:
                    price_results[item_name] = {
                        "min_sell": 0.0, "max_buy": 0.0}

    return price_results
