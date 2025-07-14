import dataclasses
import time
from typing import List, Dict


@dataclasses.dataclass
class Item:
    """Represents a single item with its name and quantity."""
    name: str
    quantity: int


@dataclasses.dataclass
class PricedItem:
    """Stores item details including the price at the time of the run."""
    name: str
    type_id: int
    quantity: int
    min_sell: float
    max_buy: float


@dataclasses.dataclass
class RunState:
    """Represents a snapshot of the inventory at a specific time."""
    timestamp: float
    items: Dict[str, Item]

    @classmethod
    def from_clipboard(cls, clipboard_content: str) -> 'RunState':
        """
        Parses clipboard content into a RunState, aggregating duplicate items
        and handling items without explicit quantities (like Blueprints).
        """
        items = {}
        for line in clipboard_content.strip().split('\n'):
            parts = line.strip().split('\t')
            name = parts[0].strip()

            # Skip empty lines
            if not name:
                continue

            quantity = 0
            # Case 1: Item with a valid quantity (e.g., "Item Name\t5")
            if len(parts) == 2 and parts[1].isdigit():
                quantity = int(parts[1])
            # Case 2: Item without a quantity (e.g., "Blueprint Name")
            elif len(parts) == 1:
                quantity = 1  # Default to quantity of 1
            else:
                # Ignore other malformed lines
                continue

            # If the item is already in our dictionary, add the new quantity
            if name in items:
                items[name].quantity += quantity
            # Otherwise, add the item to the dictionary
            else:
                items[name] = Item(name=name, quantity=quantity)

        return cls(timestamp=time.time(), items=items)


@dataclasses.dataclass
class LootRun:
    """Represents a single loot run, containing all its states and metadata."""
    start_time: float
    end_time: float = 0.0
    states: List[RunState] = dataclasses.field(default_factory=list)
    comment: str = ""
    ship_type: str = "N/A"
    ship_amount: int = 0
    weather: str = "N/A"
    tier: int = -1
    # The priced item lists are now the ONLY record of value.
    looted_items_priced: List[PricedItem] = dataclasses.field(
        default_factory=list)
    consumed_items_priced: List[PricedItem] = dataclasses.field(
        default_factory=list)

    def add_state(self, state: RunState):
        self.states.append(state)

    def get_looted_items(self) -> Dict[str, int]:
        if len(self.states) < 2:
            return {}  # Need at least a start and end state
        initial_items = self.states[0].items
        latest_items = self.states[-1].items
        looted = {}
        for name, item in latest_items.items():
            initial_qty = initial_items.get(name, Item(name, 0)).quantity
            if item.quantity > initial_qty:
                looted[name] = item.quantity - initial_qty
        return looted

    def get_consumed_items(self) -> Dict[str, int]:
        if len(self.states) < 2:
            return {}
        initial_items = self.states[0].items
        latest_items = self.states[-1].items
        consumed = {}
        for name, item in initial_items.items():
            latest_qty = latest_items.get(name, Item(name, 0)).quantity
            if item.quantity > latest_qty:
                consumed[name] = item.quantity - latest_qty
        return consumed
