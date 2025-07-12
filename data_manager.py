import sqlite3
from pathlib import Path
from typing import List
from loot_run import LootRun, PricedItem

# Use the same consolidated database path
DB_PATH = Path("./db/app_data.sqlite")


def initialize_run_db():
    """
    Initializes the database schema with normalized tables for runs, items,
    and their relationships. This function should be called once on startup.
    """
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Enable foreign key support
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Master table for all runs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time REAL UNIQUE NOT NULL,
                end_time REAL,
                comment TEXT,
                ship_type TEXT,
                ship_amount INTEGER,
                weather TEXT,
                tier INTEGER
            )
        """)

        # Master table for all unique items, using the official type_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                type_id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL
            )
        """)

        # Linking table for items in a run, referencing items.type_id
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS run_items (
                run_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                min_sell REAL NOT NULL,
                max_buy REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('looted', 'consumed')),
                FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE,
                FOREIGN KEY (type_id) REFERENCES items (type_id)
            )
        """)
        conn.commit()


def _ensure_item_exists(cursor: sqlite3.Cursor, type_id: int, item_name: str):
    """
    Inserts an item into the 'items' table if it doesn't exist.
    Uses INSERT OR IGNORE to be efficient and avoid constraint errors.
    """
    cursor.execute(
        "INSERT OR IGNORE INTO items (type_id, name) VALUES (?, ?)", (type_id, item_name))


def save_run(run: LootRun) -> int:
    """
    Saves a single loot run to the normalized database structure.
    Returns the run_id of the saved run.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        # Step 1: Insert the main run record
        cursor.execute("""
            INSERT INTO runs (start_time, end_time, comment, ship_type, ship_amount, weather, tier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            run.start_time, run.end_time, run.comment, run.ship_type,
            run.ship_amount, run.weather, run.tier
        ))
        run_id = cursor.lastrowid

        # Step 2: Process and insert looted items
        for item in run.looted_items_priced:
            _ensure_item_exists(cursor, item.type_id, item.name)
            cursor.execute("""
                INSERT INTO run_items (run_id, type_id, quantity, min_sell, max_buy, status)
                VALUES (?, ?, ?, ?, ?, 'looted')
            """, (run_id, item.type_id, item.quantity, item.min_sell, item.max_buy))

        # Step 3: Process and insert consumed items
        for item in run.consumed_items_priced:
            _ensure_item_exists(cursor, item.type_id, item.name)
            cursor.execute("""
                INSERT INTO run_items (run_id, type_id, quantity, min_sell, max_buy, status)
                VALUES (?, ?, ?, ?, ?, 'consumed')
            """, (run_id, item.type_id, item.quantity, item.min_sell, item.max_buy))

        conn.commit()
        return run_id


def load_runs() -> List[LootRun]:
    """
    Loads all loot runs from the SQLite database, reconstructing the LootRun objects
    from the normalized tables.
    """
    if not DB_PATH.exists():
        return []

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Step 1: Fetch all base run data
            cursor.execute("SELECT * FROM runs ORDER BY start_time DESC")
            run_rows = cursor.fetchall()

            runs = []
            for run_row in run_rows:
                run_data = dict(run_row)
                run_id = run_data['run_id']

                # Step 2: For each run, fetch its associated items
                item_cursor = conn.cursor()
                item_cursor.execute("""
                    SELECT i.name, ri.type_id, ri.quantity, ri.min_sell, ri.max_buy, ri.status
                    FROM run_items ri
                    JOIN items i ON ri.type_id = i.type_id
                    WHERE ri.run_id = ?
                """, (run_id,))
                item_rows = item_cursor.fetchall()

                looted_items_priced = []
                consumed_items_priced = []
                for item_row in item_rows:
                    priced_item = PricedItem(
                        name=item_row['name'],
                        type_id=item_row['type_id'],
                        quantity=item_row['quantity'],
                        min_sell=item_row['min_sell'],
                        max_buy=item_row['max_buy']
                    )
                    if item_row['status'] == 'looted':
                        looted_items_priced.append(priced_item)
                    else:  # 'consumed'
                        consumed_items_priced.append(priced_item)

                # Step 3: Construct the final LootRun object
                del run_data['run_id']  # Not a field in the LootRun dataclass
                run_data['looted_items_priced'] = looted_items_priced
                run_data['consumed_items_priced'] = consumed_items_priced
                run_data['states'] = []  # States are transient

                runs.append(LootRun(**run_data))
            return runs

    except sqlite3.OperationalError:
        # This can happen if the table doesn't exist yet.
        return []
