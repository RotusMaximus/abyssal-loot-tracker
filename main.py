import time
from datetime import datetime
import locale
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Button, RichLog, Input, Label, Select, TabbedContent, TabPane, DataTable
from textual.containers import Container, Vertical, Horizontal

from loot_run import LootRun, RunState, PricedItem
from clipboard_monitor import ClipboardMonitor, ClipboardChanged
import data_manager
import price_checker

# Set locale for number formatting
locale.setlocale(locale.LC_ALL, '')

# --- UI Options ---
SHIP_TYPE_OPTIONS = ["Frigate", "Destroyer", "Cruiser"]
WEATHER_TYPE_OPTIONS = ["Dark", "Electrical", "Exotic", "Firestorm", "Gamma"]
FRIGATE_AMOUNT_OPTIONS = ["1", "2", "3"]
DESTROYER_AMOUNT_OPTIONS = ["1", "2"]
CRUISER_AMOUNT_OPTIONS = ["1"]
TIER_OPTIONS = ["0", "1", "2", "3", "4", "5", "6"]


class LootTrackerApp(App):
    CSS_PATH = "main.css"

    def __init__(self):
        super().__init__()
        self.active_run: LootRun | None = None
        # Initialize databases for both prices and runs on startup
        price_checker.initialize_price_db()
        data_manager.initialize_run_db()
        # Load existing runs from the database
        self.runs = data_manager.load_runs()
        self.clipboard_monitor = ClipboardMonitor(self)
        self.title = "Abyssal Loot Tracker"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with TabbedContent():
            with TabPane("Current Run", id="current-run-pane"):
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
                        yield RichLog(id="run_log", wrap=True, markup=True)
                with Horizontal(id="controls"):
                    yield Button("Start Run", id="start_run", variant="success")
                    yield Button("Stop Run", id="stop_run", variant="error", disabled=True)
            with TabPane("Run History", id="run-history-pane"):
                with Container(id="app-grid"):
                    with Vertical(id="metadata-container"):
                        yield Label("Settings")
                    with Vertical(id="run-overview"):
                        yield DataTable(id="run-overview-data-table", zebra_stripes=True, cursor_type="row")

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.query_one("#run_log", RichLog).write(
            "[#EF4343]W[/#EF4343][#EFC443]e[/#EFC443][#99EF43]l[/#99EF43][#43EF6E]c[/#43EF6E][#43EFEF]o[/#43EFEF][#436EEF]m[/#436EEF][#9943EF]e[/#9943EF][#EF43C4]![/#EF43C4] Set metadata and press 'Start Run'.")
        self.clipboard_monitor.start()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Event handler for button presses."""
        if event.button.id == "start_run":
            self.start_new_run()
        elif event.button.id == "stop_run":
            await self.stop_current_run()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Dynamically update ship amount selection based on ship type."""
        if event.select.id == "ship_type_select":
            ship_amount_select = self.query_one("#ship_amount_select", Select)
            ship_type = event.value
            if ship_type == "Frigate":
                ship_amount_select.disabled = False
                ship_amount_select.set_options(
                    (option, option) for option in FRIGATE_AMOUNT_OPTIONS)
            elif ship_type == "Destroyer":
                ship_amount_select.disabled = False
                ship_amount_select.set_options(
                    (option, option) for option in DESTROYER_AMOUNT_OPTIONS)
            elif ship_type == "Cruiser":
                ship_amount_select.set_options(
                    (option, option) for option in CRUISER_AMOUNT_OPTIONS)
                ship_amount_select.value = "1"
                ship_amount_select.disabled = True

    @on(TabbedContent.TabActivated)
    def on_tabbedcontent_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Propagate run history list when the run history tab is selected."""
        if event.pane.id == "run-history-pane":
            # TODO: Rework drawing of table, so no clearing of columns is needed.
            self.query_one("#run-overview-data-table",
                           DataTable).clear(columns=True)
            all_runs = data_manager.load_runs()
            ROWS = [("Date", "Ship Type",
                     "Ship Amount", "Weather", "Tier", "Net Profit (Sell)")]
            for run in all_runs:
                total_looted_sell = sum(
                    item.min_sell * item.quantity for item in run.looted_items_priced)
                total_consumed_sell = sum(
                    item.min_sell * item.quantity for item in run.consumed_items_priced)
                net_profit = total_looted_sell - total_consumed_sell
                formatted_net_profit = locale.format_string(
                    '%.2f', net_profit, grouping=True)
                ROWS.append((f"{datetime.fromtimestamp(run.start_time).strftime('%d.%m.%Y %H:%M')}",
                            run.ship_type, run.ship_amount, run.weather, run.tier, f"{formatted_net_profit} ISK"))
            self.query_one("#run-overview-data-table",
                           DataTable).add_columns(*ROWS[0])
            self.query_one("#run-overview-data-table",
                           DataTable).add_rows(ROWS[1:])

    def start_new_run(self):
        """Starts a new loot run and updates the UI."""
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
        except (ValueError, TypeError):
            self.active_run.ship_amount = 0
        try:
            self.active_run.tier = int(
                self.query_one("#tier_select", Select).value)
        except (ValueError, TypeError):
            self.active_run.tier = -1

        # Update UI state
        log.write("--- New Run Started ---")
        log.write(
            f"Timestamp: [cyan]{time.ctime(self.active_run.start_time)}[/cyan]")
        log.write(
            f"Currently Running: [cyan]Tier {self.active_run.tier} {self.active_run.weather}[/cyan] | [cyan]{self.active_run.ship_amount}x {self.active_run.ship_type}[/cyan]")
        log.write("\nNow copy your inventory to record the first state...")
        self.query_one("#start_run", Button).disabled = True
        self.query_one("#stop_run", Button).disabled = False
        self.query_one("#comment_input", Input).disabled = False
        for widget_id in ["#ship_type_select", "#ship_amount_select", "#weather_type_select", "#tier_select"]:
            self.query_one(widget_id).disabled = True
        self.query_one("#stop_run", Button).focus()

    async def stop_current_run(self):
        """Stops the run, fetches prices, calculates value, and saves to the database."""
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
                        f" > Price for [green]'{name}'[/green] loaded from [yellow]cache[/yellow].")
                elif source == 'api':
                    log.write(
                        f" > Price for [green]'{name}'[/green]  queried from [cyan]API[/cyan].")
                elif source == "blueprint_skip":
                    log.write(
                        f" > Price query for [green]'{name}[/green]' was [blue]skipped[/blue]. "
                    )
                else:
                    log.write(
                        f" > Price for [green]'{name}'[/green] [red]not found[/red].")

            # Process looted items
            for name, qty in looted_items.items():
                price = price_data[name]
                item_value = price['min_sell'] * qty
                total_looted_sell += item_value
                # Create and store the detailed priced item
                self.active_run.looted_items_priced.append(PricedItem(
                    name=name, type_id=price['type_id'], quantity=qty, min_sell=price['min_sell'], max_buy=price['max_buy']
                ))

            # Process consumed items
            for name, qty in consumed_items.items():
                price = price_data[name]
                item_value = price['min_sell'] * qty
                total_consumed_sell += item_value
                self.active_run.consumed_items_priced.append(PricedItem(
                    name=name, type_id=price['type_id'], quantity=qty, min_sell=price['min_sell'], max_buy=price['max_buy']
                ))

        # Append to in-memory list and save the single new run to the database
        self.runs.append(self.active_run)
        data_manager.save_run(self.active_run)

        # Log the final results
        log.write("\n--- Run Ended ---")
        log.write(f"Comment: {self.active_run.comment}")
        log.write(f"Looted Items:")
        for name, qty in looted_items.items():
            log.write(f"[green]{name}[/green]: [cyan]{qty}[/cyan]")
        log.write(f"\nConsumed Items:")
        for name, qty in consumed_items.items():
            log.write(f"[green]{name}[/green]: [cyan]{qty}[/cyan]")
        formatted_total_looted_sell = locale.format_string(
            '%.2f', total_looted_sell, grouping=True)
        formatted_total_consumed_sell = locale.format_string(
            '%.2f', total_consumed_sell, grouping=True)
        log.write(
            f"\n[bold green]Total Loot Value (Sell):[/bold green] [bold cyan]{formatted_total_looted_sell}[/bold cyan] ISK")
        log.write(
            f"[bold red]Total Consumed Value (Sell):[/bold red] [bold cyan]{formatted_total_consumed_sell}[/bold cyan] ISK")
        net_profit = total_looted_sell - total_consumed_sell
        formatted_net_profit = locale.format_string(
            '%.2f', net_profit, grouping=True)
        profit_color = "green" if net_profit >= 0 else "red"
        log.write(
            f"\n--- [bold {profit_color}]Net Profit (Sell): {formatted_net_profit}[/bold {profit_color}]  ISK ---")

        # Reset UI for the next run
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
        """Handles clipboard updates to record inventory states."""
        if self.active_run:
            new_state = RunState.from_clipboard(message.content)
            self.active_run.add_state(new_state)
            log = self.query_one("#run_log", RichLog)
            if len(self.active_run.states) == 1:
                log.write("--- Initial inventory state recorded. ---")
            else:
                log.write(
                    f"\n--- Inventory state updated at [cyan]{time.ctime(new_state.timestamp)}[/cyan] ---")

            for item in new_state.items.values():
                log.write(
                    f"[green]{item.name}[/green]: [cyan]{item.quantity}[/cyan]")


if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
