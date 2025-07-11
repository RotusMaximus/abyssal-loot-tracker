import json
import dataclasses
from typing import List
# We need to import the data models to reconstruct them
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
    Loads loot runs from a JSON file, handling both old and new data formats.
    """
    try:
        with open(filename, 'r') as f:
            raw_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    runs = []
    for run_data in raw_data:
        # Check for the new format by seeing if 'looted_items_priced' exists
        if 'looted_items_priced' in run_data:
            # Pop the lists of dictionaries from the main data dict
            looted_dicts = run_data.pop('looted_items_priced', [])
            consumed_dicts = run_data.pop('consumed_items_priced', [])

            # Reconstruct the PricedItem objects
            looted_items = [PricedItem(**d) for d in looted_dicts]
            consumed_items = [PricedItem(**d) for d in consumed_dicts]

            # Create the LootRun object from the remaining flat data
            run = LootRun(**run_data)
            # Assign the reconstructed object lists
            run.looted_items_priced = looted_items
            run.consumed_items_priced = consumed_items
            runs.append(run)
        else:
            # Handle old format: simply create the object.
            # The priced lists will be empty by default.
            runs.append(LootRun(**run_data))

    return runs
