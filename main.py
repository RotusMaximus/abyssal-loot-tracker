import time
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Static, RichLog, Input
from textual.containers import Container, Vertical, Horizontal
from loot_run import LootRun, RunState
from clipboard_monitor import ClipboardMonitor, ClipboardChanged
import data_manager


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
        """Create child widgets for the app."""
        yield Header()
        with Container():
            yield RichLog(id="run_log", wrap=True, highlight=True)
            with Horizontal(id="controls"):
                yield Button("Start Run", id="start_run", variant="success")
                yield Button("Stop Run", id="stop_run", variant="error", disabled=True)
        yield Input(placeholder="Add a comment...", id="comment_input", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.query_one("#run_log").write("Welcome to Loot Tracker!")
        self.clipboard_monitor.start()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "start_run":
            self.start_new_run()
        elif event.button.id == "stop_run":
            self.stop_current_run()

    def start_new_run(self):
        """Starts a new loot run."""
        self.active_run = LootRun(start_time=time.time())
        self.query_one("#run_log").clear()
        self.query_one("#run_log").write(
            f"Loot run started at {time.ctime(self.active_run.start_time)}")
        self.query_one("#start_run").disabled = True
        self.query_one("#stop_run").disabled = False
        self.query_one("#comment_input").disabled = False

    def stop_current_run(self):
        """Stops and saves the current loot run."""
        if self.active_run:
            self.active_run.end_time = time.time()
            self.active_run.comment = self.query_one("#comment_input").value
            self.runs.append(self.active_run)
            data_manager.save_runs(self.runs)

            log = self.query_one("#run_log")
            log.write("\n--- Run Ended ---")
            log.write(f"Comment: {self.active_run.comment}")
            log.write(f"Looted Items: {self.active_run.get_looted_items()}")
            log.write(
                f"Consumed Items: {self.active_run.get_consumed_items()}")

            self.active_run = None
            self.query_one("#start_run").disabled = False
            self.query_one("#stop_run").disabled = True
            self.query_one("#comment_input").disabled = True
            self.query_one("#comment_input").value = ""

    async def on_clipboard_changed(self, message: ClipboardChanged) -> None:
        """Handle clipboard change messages."""
        if self.active_run:
            new_state = RunState.from_clipboard(message.content)
            self.active_run.add_state(new_state)
            log = self.query_one("#run_log")
            log.write(
                f"\n--- Clipboard updated at {time.ctime(new_state.timestamp)} ---")
            for item in new_state.items.values():
                log.write(f"{item.name}: {item.quantity}")

    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark


if __name__ == "__main__":
    app = LootTrackerApp()
    app.run()
