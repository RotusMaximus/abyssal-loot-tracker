from textual.message import Message
import time
import pyperclip
from textual.app import App


class ClipboardMonitor:
    """A monitor that polls the clipboard for changes."""

    def __init__(self, app: App, interval: float = 1.0):
        self.app = app
        self.interval = interval
        self._last_content = ""
        self.running = False

    def start(self):
        """Starts the clipboard monitoring."""
        if not self.running:
            self.running = True
            self._last_content = pyperclip.paste()
            self.app.set_interval(self.interval, self.poll_clipboard)

    def stop(self):
        """Stops the clipboard monitoring."""
        self.running = False

    def poll_clipboard(self):
        """Polls the clipboard and posts a message if it has changed."""
        if not self.running:
            return

        try:
            current_content = pyperclip.paste()
            if current_content != self._last_content:
                self._last_content = current_content
                self.app.post_message(ClipboardChanged(current_content))
        except pyperclip.PyperclipException:
            # Handle cases where clipboard access might fail
            pass


class ClipboardChanged(Message):
    """A message to indicate the clipboard content has changed."""

    def __init__(self, content: str) -> None:
        self.content = content
        super().__init__()
