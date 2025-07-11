import time
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, RichLog, Input, RadioSet, RadioButton, Label
from textual.containers import Container, Vertical, Horizontal

from loot_run import LootRun, RunState
from clipboard_monitor import ClipboardMonitor, ClipboardChanged
import data_manager
import price_checker  # Import the new module


class LootTrackerApp(App):
    """A TUI application for tracking loot runs."""

    CSS_PATH = "main.css"
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def __init__(self):
        super().__init__()
        self.active_run: LootRun | None = None
        self.runs = data_manager.load_runs()
        self.clipboard_monitor = ClipboardMonitor(self)

    def compose(self) -> ComposeResult:
        # This function's content is unchanged from the previous version
        yield Header()
        with Container(id="app-grid"):
            with Vertical(id="metadata-container"):
                yield Label("Ship Type:")
                with RadioSet(id="ship_type_select"):
                    yield RadioButton("Frigate", id="frigate")
                    yield RadioButton("Destroyer", id="destroyer")
                    yield RadioButton("Cruiser", id="cruiser")

                yield Label("Ship Amount:")
                yield Input(placeholder="1-3", id="ship_amount_input")

                yield Label("Weather:")
                with RadioSet(id="weather_select"):
                    yield RadioButton("Dark")
                    yield RadioButton("Electrical")
                    yield RadioButton("Exotic")
                    yield RadioButton("Firestorm")
                    yield RadioButton("Gamma")

                yield Label("Tier:")
                yield Input(placeholder="0-6", id="tier_input")

            with Vertical(id="run-container"):
                yield RichLog(id="run_log", wrap=True, highlight=True)
                yield Input(placeholder="Add a comment...", id="comment_input", disabled=True)

        with Horizontal(id="controls"):
            yield Button("Start Run", id="start_run", variant="success")
            yield Button("Stop Run", id="stop_run", variant="error", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        price_checker.initialize_price_db()  # Initialize the price cache DB
        self.query_one("#run_log").write(
            "Welcome! Set metadata and press 'Start Run'.")
        self.clipboard_monitor.start()

    # Make this handler async to allow awaiting
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "start_run":
            self.start_new_run()
        elif event.button.id == "stop_run":
            await self.stop_current_run()  # Await the async stop method

    # Incorporating your submitted fix
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Dynamically update ship amount constraints based on ship type."""
        if event.radio_set.id == "ship_type_select":
            ship_amount_input = self.query_one("#ship_amount_input", Input)
            if event.radio_set.id == "frigate":
                ship_amount_input.placeholder = "1-3"
            elif event.radio_set.id == "destroyer":
                ship_amount_input.placeholder = "1-2"
            elif event.radio_set.id == "cruiser":
                ship_amount_input.placeholder = "1 (fixed)"

    def start_new_run(self):
        # This function's content is unchanged
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
        """Stops the run, fetches prices, calculates value, and saves."""
        if not self.active_run:
            return

        log = self.query_one("#run_log")
        self.active_run.end_time = time.time()
        self.active_run.comment = self.query_one("#comment_input").value

        looted_items = self.active_run.get_looted_items()
        consumed_items = self.active_run.get_consumed_items()

        if not looted_items and not consumed_items:
            log.write("No items were looted or consumed.")
        else:
            log.write("\n--- Fetching Prices (this may take a moment)... ---")
            unique_item_names = list(
                set(looted_items.keys()) | set(consumed_items.keys()))
            price_data = await price_checker.get_prices_for_items(unique_item_names)
            log.write("--- Price fetch complete. Calculating value... ---")

            # Calculate looted value
            for name, qty in looted_items.items():
                self.active_run.total_looted_value_sell += price_data[name]['min_sell'] * qty
                self.active_run.total_looted_value_buy += price_data[name]['max_buy'] * qty

            # Calculate consumed value
            for name, qty in consumed_items.items():
                self.active_run.total_consumed_value_sell += price_data[name]['min_sell'] * qty
                self.active_run.total_consumed_value_buy += price_data[name]['max_buy'] * qty

        # Append and save the completed run object with all data
        self.runs.append(self.active_run)
        data_manager.save_runs(self.runs)

        log.write("\n--- Run Ended ---")
        log.write(f"Comment: {self.active_run.comment}")
        log.write(f"Looted Items: {looted_items}")
        log.write(f"Consumed Items: {consumed_items}")
        log.write(
            f"[bold green]Total Loot Value (Sell):[/] {self.active_run.total_looted_value_sell:,.2f} ISK")
        log.write(
            f"[bold red]Total Consumed Value (Sell):[/] {self.active_run.total_consumed_value_sell:,.2f} ISK")
        net_profit = self.active_run.total_looted_value_sell - \
            self.active_run.total_consumed_value_sell
        profit_color = "green" if net_profit >= 0 else "red"
        log.write(
            f"--- [bold {profit_color}]Net Profit (Sell): {net_profit:,.2f} ISK[/] ---")

        # Reset UI
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

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark


if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
