
from abyssal_tracker.main import LootTrackerApp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
