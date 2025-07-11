import json
import dataclasses
from typing import List
from loot_run import LootRun, PricedItem


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
    """
    Loads loot runs from a JSON file using the new, clean format.
    """
    try:
        with open(filename, 'r') as f:
            raw_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    runs = []
    for run_data in raw_data:
        # Reconstruct the nested PricedItem objects first.
        looted_items = [PricedItem(**d)
                        for d in run_data.get('looted_items_priced', [])]
        consumed_items = [PricedItem(
            **d) for d in run_data.get('consumed_items_priced', [])]

        # Create the main LootRun object from the other keys.
        run_flat_data = {k: v for k, v in run_data.items() if k not in [
            'looted_items_priced', 'consumed_items_priced']}
        run = LootRun(**run_flat_data)

        # Assign the reconstructed lists to the new LootRun object.
        run.looted_items_priced = looted_items
        run.consumed_items_priced = consumed_items
        runs.append(run)

    return runs
