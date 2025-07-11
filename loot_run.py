import dataclasses
import time
from typing import List, Dict


@dataclasses.dataclass
class Item:
    """Represents a single item with its name and quantity."""
    name: str
    quantity: int


@dataclasses.dataclass
class RunState:
    """Represents a snapshot of the inventory at a specific time."""
    timestamp: float
    items: Dict[str, Item]

    @classmethod
    def from_clipboard(cls, clipboard_content: str) -> 'RunState':
        """Parses clipboard content to create a RunState."""
        items = {}
        for line in clipboard_content.strip().split('\n'):
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) == 2 and parts[1].isdigit():
                    name = parts[0].strip()
                    quantity = int(parts[1])
                    items[name] = Item(name=name, quantity=quantity)
        return cls(timestamp=time.time(), items=items)


@dataclasses.dataclass
class LootRun:
    """Represents a single loot run, containing all its states and metadata."""
    start_time: float
    end_time: float = 0.0
    states: List[RunState] = dataclasses.field(default_factory=list)
    comment: str = ""

    def add_state(self, state: RunState):
        """Adds a new state to the run."""
        self.states.append(state)

    def get_looted_items(self) -> Dict[str, int]:
        """Calculates the items looted during the run."""
        if not self.states:
            return {}

        initial_items = self.states[0].items
        latest_items = self.states[-1].items
        looted = {}

        for name, item in latest_items.items():
            if name not in initial_items:
                looted[name] = item.quantity
            elif name in initial_items and item.quantity > initial_items[name].quantity:
                looted[name] = item.quantity - initial_items[name].quantity
        return looted

    def get_consumed_items(self) -> Dict[str, int]:
        """Calculates the items consumed during the run."""
        if not self.states:
            return {}

        initial_items = self.states[0].items
        latest_items = self.states[-1].items
        consumed = {}

        for name, item in initial_items.items():
            if name not in latest_items:
                consumed[name] = item.quantity
            # --- THIS IS THE CORRECTED LOGIC ---
            elif name in latest_items and latest_items[name].quantity < item.quantity:
                consumed[name] = item.quantity - latest_items[name].quantity
        return consumed
