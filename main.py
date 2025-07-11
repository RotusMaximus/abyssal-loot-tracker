import time
import locale
from textual.app import App, ComposeResult
from textual.widgets import Header, Button, RichLog, Input, Label, Select
from textual.containers import Container, Vertical, Horizontal

from loot_run import LootRun, RunState, PricedItem
from clipboard_monitor import ClipboardMonitor, ClipboardChanged
import data_manager
import price_checker

locale.setlocale(locale.LC_ALL, '')

SHIP_TYPE_OPTIONS = """Frigate
Destroyer
Cruiser
""".splitlines()

WEATHER_TYPE_OPTIONS = """Dark
Electrical
Exotic
Firestorm
Gamma
""".splitlines()

FRIGATE_AMOUNT_OPTIONS = """1
2
3
""".splitlines()

DESTROYER_AMOUNT_OPTIONS = """1
2
""".splitlines()

CRUISER_AMOUNT_OPTIONS = """1
""".splitlines()

TIER_OPTIONS = """0
1
2
3
4
5
6
""".splitlines()


class LootTrackerApp(App):
    CSS_PATH = "main.css"

    def __init__(self):
        super().__init__()
        self.active_run: LootRun | None = None
        self.runs = data_manager.load_runs()
        self.clipboard_monitor = ClipboardMonitor(self)
        self.title = "Abyssal Loot Tracker"

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="metadata-container"):
                yield Label("Ship Type:")
                yield Select(((option, option) for option in SHIP_TYPE_OPTIONS), value="Cruiser", id="ship_type_select", allow_blank=False)
                yield Label("Ship Amount:")
                yield Select(((option, option) for option in CRUISER_AMOUNT_OPTIONS), value="1", disabled=True, id="ship_amount_select", allow_blank=False)
                yield Label("Weather:")
                yield Select(((option, option) for option in WEATHER_TYPE_OPTIONS), id="weather_type_select", allow_blank=False)
                yield Label("Tier:")
                yield Select(((option, option) for option in TIER_OPTIONS), id="tier_select", allow_blank=False)
                yield Label("Comment:")
                yield Input(placeholder="Add a comment...", id="comment_input")
            with Vertical(id="run-container"):
                yield RichLog(id="run_log", wrap=True, markup=True, highlight=True)
        with Horizontal(id="controls"):
            yield Button("Start Run", id="start_run", variant="success")
            yield Button("Stop Run", id="stop_run", variant="error", disabled=True)

    def on_mount(self) -> None:
        price_checker.initialize_price_db()
        self.query_one("#run_log", RichLog).write(
            "Welcome! Set metadata and press 'Start Run'.")
        self.clipboard_monitor.start()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start_run":
            self.start_new_run()
        elif event.button.id == "stop_run":
            await self.stop_current_run()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Dynamically update ship amount selection offerings based on ship type."""
        if event.select.id == "ship_type_select":
            ship_amount_select = self.query_one("#ship_amount_select", Select)
            if event.select.value == "Frigate":
                ship_amount_select.disabled = False
                ship_amount_select.set_options(
                    (option, option) for option in FRIGATE_AMOUNT_OPTIONS)
            elif event.select.value == "Destroyer":
                ship_amount_select.disabled = False
                ship_amount_select.set_options(
                    (option, option) for option in DESTROYER_AMOUNT_OPTIONS)
            elif event.select.value == "Cruiser":
                ship_amount_select.disabled = True
                ship_amount_select.value = "1"

    def start_new_run(self):
        self.active_run = LootRun(start_time=time.time())
        log = self.query_one("#run_log", RichLog)
        log.clear()
        ship_type_set = self.query_one("#ship_type_select", Select)
        if ship_type_set.selection:
            self.active_run.ship_type = ship_type_set.selection
        weather_set = self.query_one("#weather_type_select", Select)
        if weather_set.selection:
            self.active_run.weather = weather_set.selection
        try:
            self.active_run.ship_amount = int(
                self.query_one("#ship_amount_select", Select).value)
        except ValueError:
            self.active_run.ship_amount = 0
        try:
            tier = int(self.query_one("#tier_select", Select).value)
            self.active_run.tier = tier if 0 <= tier <= 6 else -1
        except ValueError:
            self.active_run.tier = -1
        log.write("--- New Run Started ---")
        log.write(f"Timestamp: {time.ctime(self.active_run.start_time)}")
        log.write(
            f"Metadata: Tier {self.active_run.tier} {self.active_run.weather} | {self.active_run.ship_amount}x {self.active_run.ship_type}")
        log.write("\nNow copy your inventory to record the first state...")
        self.query_one("#start_run", Button).disabled = True
        self.query_one("#stop_run", Button).disabled = False
        self.query_one("#comment_input", Input).disabled = False
        for widget_id in ["#ship_type_select", "#ship_amount_select", "#weather_type_select", "#tier_select"]:
            self.query_one(widget_id).disabled = True
        self.query_one("#stop_run", Button).focus()

    async def stop_current_run(self):
        """Stops the run, fetches prices with logging, calculates value, and saves."""
        if not self.active_run:
            return

        log = self.query_one("#run_log", RichLog)
        self.active_run.end_time = time.time()
        self.active_run.comment = self.query_one("#comment_input", Input).value

        looted_items = self.active_run.get_looted_items()
        consumed_items = self.active_run.get_consumed_items()
        unique_item_names = list(
            set(looted_items.keys()) | set(consumed_items.keys()))

        total_looted_sell, total_consumed_sell = 0.0, 0.0

        if unique_item_names:
            log.write("\n--- Fetching Prices... ---")
            price_data = await price_checker.get_prices_for_items(unique_item_names)

            # Log the source of each price
            for name, data in price_data.items():
                source = data['source']
                if source == 'cache':
                    log.write(
                        f" > Price for '{name}' loaded from [yellow]cache[/yellow].")
                elif source == 'api':
                    log.write(
                        f" > Price for '{name}' queried from [cyan]API[/cyan].")
                else:
                    log.write(f" > Price for '{name}' [red]not found[/red].")

            # Process looted items
            for name, qty in looted_items.items():
                price = price_data[name]
                item_value = price['min_sell'] * qty
                total_looted_sell += item_value
                # Create and store the detailed priced item
                self.active_run.looted_items_priced.append(PricedItem(
                    name=name, quantity=qty, min_sell=price['min_sell'], max_buy=price['max_buy']
                ))

            # Process consumed items
            for name, qty in consumed_items.items():
                price = price_data[name]
                item_value = price['min_sell'] * qty
                total_consumed_sell += item_value
                self.active_run.consumed_items_priced.append(PricedItem(
                    name=name, quantity=qty, min_sell=price['min_sell'], max_buy=price['max_buy']
                ))

        self.runs.append(self.active_run)
        data_manager.save_runs(self.runs)

        log.write("\n--- Run Ended ---")
        log.write(f"Comment: {self.active_run.comment}")
        log.write(f"Looted Items: {looted_items}")
        log.write(f"Consumed Items: {consumed_items}")
        formatted_total_looted_sell = locale.format_string(
            '%.2f', total_looted_sell, grouping=True)
        formatted_total_consumed_sell = locale.format_string(
            '%.2f', total_consumed_sell, grouping=True)
        log.write(
            f"\n[bold green]Total Loot Value (Sell):[/bold green] {formatted_total_looted_sell} ISK")
        log.write(
            f"[bold red]Total Consumed Value (Sell):[/bold red] {formatted_total_consumed_sell} ISK")
        net_profit = total_looted_sell - total_consumed_sell
        formatted_net_profit = locale.format_string(
            '%.2f', net_profit, grouping=True)
        profit_color = "green" if net_profit >= 0 else "red"
        log.write(
            f"\n--- [bold {profit_color}]Net Profit (Sell): {formatted_net_profit} ISK[/bold {profit_color}] ---")

        self.active_run = None
        self.query_one("#start_run", Button).disabled = False
        self.query_one("#stop_run", Button).disabled = True
        self.query_one("#comment_input", Input).disabled = True
        self.query_one("#comment_input", Input).value = ""
        for widget_id in ["#ship_type_select", "#weather_type_select", "#tier_select"]:
            self.query_one(widget_id).disabled = False
        if self.query_one("#ship_amount_select", Select).selection == "Cruiser":
            self.query_one("#ship_amount_select", Select).disabled = True

    async def on_clipboard_changed(self, message: ClipboardChanged) -> None:
        if self.active_run:
            new_state = RunState.from_clipboard(message.content)
            self.active_run.add_state(new_state)
            log = self.query_one("#run_log", RichLog)
            if len(self.active_run.states) == 1:
                log.write("--- Initial inventory state recorded. ---")
            else:
                log.write(
                    f"\n--- Clipboard updated at {time.ctime(new_state.timestamp)} ---")
            for item in new_state.items.values():
                log.write(f"{item.name}: {item.quantity}")


if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
