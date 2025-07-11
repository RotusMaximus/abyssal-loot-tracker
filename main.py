import time
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, RichLog, Input, RadioSet, RadioButton, Label
from textual.containers import Container, Vertical, Horizontal

from loot_run import LootRun, RunState, PricedItem  # Import PricedItem
from clipboard_monitor import ClipboardMonitor, ClipboardChanged
import data_manager
import price_checker


class LootTrackerApp(App):
    CSS_PATH = "main.css"

    def __init__(self):
        super().__init__()
        self.active_run: LootRun | None = None
        self.runs = data_manager.load_runs()
        self.clipboard_monitor = ClipboardMonitor(self)
        self.title = "Abyssal Loot Tracker"

    # compose, on_mount, on_button_pressed, on_radio_set_changed, start_new_run are unchanged
    # ... (Keep the code from the previous version for these methods) ...
    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="metadata-container"):
                yield Label("Ship Type:")
                with RadioSet(id="ship_type_select"):
                    yield RadioButton("Frigate", id="frigate")
                    yield RadioButton("Destroyer", id="destroyer")
                    yield RadioButton("Cruiser", id="cruiser", value=True)
                yield Label("Ship Amount:")
                yield Input(id="ship_amount_input", value="1", disabled=True)
                yield Label("Weather:")
                with RadioSet(id="weather_select"):
                    yield RadioButton("Dark")
                    yield RadioButton("Electrical")
                    yield RadioButton("Exotic")
                    yield RadioButton("Firestorm")
                    yield RadioButton("Gamma")
                yield Label("Tier:")
                yield Input(placeholder="0-6", id="tier_input")
                yield Label("Comment:")
                yield Input(placeholder="Add a comment...", id="comment_input")
            with Vertical(id="run-container"):
                yield RichLog(id="run_log", wrap=True, markup=True)
        with Horizontal(id="controls"):
            yield Button("Start Run", id="start_run", variant="success")
            yield Button("Stop Run", id="stop_run", variant="error", disabled=True)

    def on_mount(self) -> None:
        price_checker.initialize_price_db()
        self.query_one("#run_log").write(
            "Welcome! Set metadata and press 'Start Run'.")
        self.clipboard_monitor.start()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start_run":
            self.start_new_run()
        elif event.button.id == "stop_run":
            await self.stop_current_run()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Dynamically update ship amount constraints based on ship type."""
        if event.radio_set.id == "ship_type_select":
            ship_amount_input = self.query_one("#ship_amount_input", Input)
            if event.pressed.id == "frigate":
                ship_amount_input.disabled = False
                ship_amount_input.value = ""
                ship_amount_input.placeholder = "1-3"
            elif event.pressed.id == "destroyer":
                ship_amount_input.disabled = False
                ship_amount_input.value = ""
                ship_amount_input.placeholder = "1-2"
            elif event.pressed.id == "cruiser":
                ship_amount_input.value = "1"
                ship_amount_input.disabled = True

    def start_new_run(self):
        self.active_run = LootRun(start_time=time.time())
        log = self.query_one("#run_log")
        log.clear()
        ship_type_set = self.query_one("#ship_type_select", RadioSet)
        if ship_type_set.pressed_button:
            self.active_run.ship_type = ship_type_set.pressed_button.label.plain
        weather_set = self.query_one("#weather_select", RadioSet)
        if weather_set.pressed_button:
            self.active_run.weather = weather_set.pressed_button.label.plain
        try:
            self.active_run.ship_amount = int(
                self.query_one("#ship_amount_input").value)
        except ValueError:
            self.active_run.ship_amount = 0
        try:
            tier = int(self.query_one("#tier_input").value)
            self.active_run.tier = tier if 0 <= tier <= 6 else -1
        except ValueError:
            self.active_run.tier = -1
        log.write("--- New Run Started ---")
        log.write(f"Timestamp: {time.ctime(self.active_run.start_time)}")
        log.write(
            f"Metadata: Tier {self.active_run.tier} {self.active_run.weather} | {self.active_run.ship_amount}x {self.active_run.ship_type}")
        log.write("\nNow copy your inventory to record the first state...")
        self.query_one("#start_run").disabled = True
        self.query_one("#stop_run").disabled = False
        self.query_one("#comment_input").disabled = False
        for widget_id in ["#ship_type_select", "#ship_amount_input", "#weather_select", "#tier_input"]:
            self.query_one(widget_id).disabled = True

    async def stop_current_run(self):
        """Stops the run, fetches prices with logging, calculates value, and saves."""
        if not self.active_run:
            return

        log = self.query_one("#run_log")
        self.active_run.end_time = time.time()
        self.active_run.comment = self.query_one("#comment_input").value

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
        log.write(
            f"[bold green]Total Loot Value (Sell):[/bold green] {total_looted_sell:,.2f} ISK")
        log.write(
            f"[bold red]Total Consumed Value (Sell):[/bold red] {total_consumed_sell:,.2f} ISK")
        net_profit = total_looted_sell - total_consumed_sell
        profit_color = "green" if net_profit >= 0 else "red"
        log.write(
            f"--- [bold {profit_color}]Net Profit (Sell): {net_profit:,.2f} ISK[/bold {profit_color}] ---")

        self.active_run = None
        self.query_one("#start_run").disabled = False
        self.query_one("#stop_run").disabled = True
        self.query_one("#comment_input").disabled = True
        self.query_one("#comment_input").value = ""
        for widget_id in ["#ship_type_select", "#ship_amount_input", "#weather_select", "#tier_input"]:
            self.query_one(widget_id).disabled = False

    async def on_clipboard_changed(self, message: ClipboardChanged) -> None:
        if self.active_run:
            new_state = RunState.from_clipboard(message.content)
            self.active_run.add_state(new_state)
            log = self.query_one("#run_log")
            if len(self.active_run.states) == 1:
                log.write("--- Initial inventory state recorded. ---")
            else:
                log.write(
                    f"\n--- Clipboard updated at {time.ctime(new_state.timestamp)} ---")
            for item in new_state.items.values():
                log.write(f"{item.name}: {item.quantity}")

    # def action_toggle_dark(self) -> None:
    #     self.dark = not self.dark


if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
