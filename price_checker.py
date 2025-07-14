import sqlite3
import time
import httpx
import asyncio
from pathlib import Path
from typing import Dict, Tuple, Optional, Union

# --- Configuration ---
BASE_API_URL = "https://evetycoon.com/api"
REGION_ID = 10000002
SDE_DB_PATH = Path("./db/eve-sde-2025-07-07.sqlite")
APP_DB_PATH = Path("./db/app_data.sqlite")
CACHE_DURATION_SECONDS = 4 * 60 * 60  # 4 hours

# --- Database Management ---


def initialize_price_db():
    """
    Ensures the database directory and the 'prices' table exist.
    """
    APP_DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(APP_DB_PATH) as conn:
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
    """
    Retrieves the type ID for a given item name from the EVE SDE database.
    """
    if not SDE_DB_PATH.exists():
        # Consider logging this error
        return None
    try:
        with sqlite3.connect(SDE_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT typeID FROM invTypes WHERE typeName=?", (item_name,))
            result = cursor.fetchone()
            return result[0] if result else None
    except sqlite3.Error:
        # Consider logging this error
        return None


# --- Caching and API Logic ---

def get_cached_price(type_id: int) -> Optional[Tuple[float, float]]:
    """
    Retrieves a cached price from the database if it's not expired.
    """
    try:
        with sqlite3.connect(APP_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT min_sell, max_buy, last_updated FROM prices WHERE type_id=?", (type_id,))
            result = cursor.fetchone()
            if result:
                min_sell, max_buy, last_updated = result
                if time.time() - last_updated < CACHE_DURATION_SECONDS:
                    return min_sell, max_buy
    except sqlite3.Error:
        # Consider logging this error
        pass
    return None


def update_cached_price(type_id: int, min_sell: float, max_buy: float):
    """
    Inserts or updates a price in the cache database.
    """
    with sqlite3.connect(APP_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prices (type_id, min_sell, max_buy, last_updated)
            VALUES (?, ?, ?, ?)
        """, (type_id, min_sell, max_buy, int(time.time())))
        conn.commit()


def _to_finite_float(value) -> float:
    """Converts a value to a finite float, defaulting to 0.0 on any failure."""
    if value is None:
        return 0.0
    try:
        f_val = float(value)
        # Check for 'inf', '-inf', or 'nan'
        if f_val != f_val or f_val == float('inf') or f_val == float('-inf'):
            return 0.0
        return f_val
    except (ValueError, TypeError):
        return 0.0


async def fetch_price_from_api(session: httpx.AsyncClient, type_id: int) -> Optional[Tuple[float, float]]:
    """
    Fetches the price for a single item type from the API, sanitizing the output.
    """
    url = f"{BASE_API_URL}/v1/market/stats/{REGION_ID}/{type_id}"
    try:
        response = await session.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        min_sell = _to_finite_float(data.get("minSell"))
        max_buy = _to_finite_float(data.get("maxBuy"))
        return min_sell, max_buy
    except (httpx.RequestError, Exception):
        # Consider logging this error
        return None

# --- Main Public Function ---


async def get_prices_for_items(item_names: list[str]) -> Dict[str, Dict[str, Union[float, str, int]]]:
    """
    Gets prices for a list of items, using the cache and making API calls as needed.
    Skips API calls for Blueprint items, defaulting their value to 0.
    """
    price_results = {}
    items_to_fetch_api = {}

    # First, check for all items in the SDE and cache
    for name in item_names:
        # If item is a blueprint, skip API/cache and default to 0 value
        if "Blueprint" in name:
            type_id = get_type_id_from_sde(name)
            price_results[name] = {
                "min_sell": 0.0,
                "max_buy": 0.0,
                "source": "blueprint_skip",
                "type_id": type_id or 0
            }
            continue

        type_id = get_type_id_from_sde(name)
        if not type_id:
            price_results[name] = {"min_sell": 0.0,
                                   "max_buy": 0.0, "source": "not_found", "type_id": 0}
            continue

        cached = get_cached_price(type_id)
        if cached:
            price_results[name] = {"min_sell": cached[0],
                                   "max_buy": cached[1], "source": "cache", "type_id": type_id}
        else:
            # If not in cache, add to the list for API fetching
            items_to_fetch_api[name] = type_id

    # If there are any items that were not in the cache, fetch them from the API
    if items_to_fetch_api:
        async with httpx.AsyncClient() as session:
            tasks = [fetch_price_from_api(session, type_id)
                     for type_id in items_to_fetch_api.values()]
            api_price_tuples = await asyncio.gather(*tasks)

            # Process the results from the API calls
            for item_name, type_id, price_tuple in zip(items_to_fetch_api.keys(), items_to_fetch_api.values(), api_price_tuples):
                if price_tuple:
                    min_sell, max_buy = price_tuple
                    price_results[item_name] = {
                        "min_sell": min_sell, "max_buy": max_buy, "source": "api", "type_id": type_id}
                    # Update the cache with the new price
                    update_cached_price(type_id, min_sell, max_buy)
                else:
                    # Handle cases where the API call failed
                    price_results[item_name] = {
                        "min_sell": 0.0, "max_buy": 0.0, "source": "api_fail", "type_id": type_id}

    return price_results
