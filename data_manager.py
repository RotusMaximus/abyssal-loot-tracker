import json
import dataclasses
from typing import List
from loot_run import LootRun


class EnhancedJSONEncoder(json.JSONEncoder):
    """A custom JSON encoder to handle dataclasses."""

    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


def save_runs(runs: List[LootRun], filename: str = "loot_runs.json"):
    """Saves a list of loot runs to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(runs, f, cls=EnhancedJSONEncoder, indent=4)


def load_runs(filename: str = "loot_runs.json") -> List[LootRun]:
    """Loads loot runs from a JSON file."""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            # This is a simplified deserialization. For more complex needs,
            # you might need a more robust solution.
            return [LootRun(**run_data) for run_data in data]
    except FileNotFoundError:
        return []
