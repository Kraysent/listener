import enum
from typing import Callable
import rumps

class State(enum.Enum):
    STARTUP = "startup"
    READY_TO_LISTEN = "ready_to_listen"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    ERROR = "error"

_initial_menu_key = "Status: Loading model..."

def _get_error_icon(has_message: bool) -> str:
    return "⚠️" if has_message else "🎤"

_STATE_CONFIG: dict[State, tuple[str, str | Callable[[bool], str]]] = {
    State.STARTUP: ("Loading model...", "🎤"),
    State.READY_TO_LISTEN: ("Ready - Press Right Option to record", "🎤"),
    State.LISTENING: ("Recording...", "🔴"),
    State.TRANSCRIBING: ("Transcribing...", "⏳"),
    State.ERROR: ("Error", _get_error_icon),
}

class App(rumps.App):
    def __init__(self, on_quit: Callable[[], None]):
        super().__init__("Listener", "🎤", menu=[rumps.MenuItem("Status: Loading model...")], quit_button=None)
        self.on_quit_callback = on_quit
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit_handler))

    def set_state(self, state: State, message: str = "") -> None:
        config = _STATE_CONFIG.get(state)
        if config is None:
            return
        
        default_status, icon_config = config
        
        status_text = message if message else default_status
        
        if callable(icon_config):
            icon = icon_config(bool(message))
        else:
            icon = icon_config
        
        if self.menu and len(self.menu) > 0:
            menu_item = self.menu.get(_initial_menu_key)
            if menu_item:
                menu_item.title = f"Status: {status_text}"
        
        self.title = icon

    def _quit_handler(self, _) -> None:
        self.on_quit_callback()
        rumps.quit_application()
