import enum
from typing import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class StateConfig:
    status: str
    icon: str | Callable[[bool], str]


_STATE_CONFIG: dict[State, StateConfig] = {
    State.STARTUP: StateConfig("Starting...", "🎤"),
    State.READY_TO_LISTEN: StateConfig("Ready - Press Right Option to record", "🎤"),
    State.LISTENING: StateConfig("Recording...", "🔴"),
    State.TRANSCRIBING: StateConfig("Transcribing...", "⏳"),
    State.ERROR: StateConfig("Error", _get_error_icon),
}


class App(rumps.App):
    def __init__(self, on_quit: Callable[[], None]):
        super().__init__(
            "Listener",
            "🎤",
            menu=[rumps.MenuItem(_STATE_CONFIG[State.STARTUP].status)],
            quit_button=None,
        )

        self.on_quit_callback = on_quit
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit_handler))

    def set_state(self, state: State, message: str = "") -> None:
        config = _STATE_CONFIG.get(state)
        if config is None:
            return

        icon_config = config.icon
        if callable(icon_config):
            icon = icon_config(bool(message))
        else:
            icon = icon_config

        self.title = icon

    def _quit_handler(self, _) -> None:
        self.on_quit_callback()
        rumps.quit_application()
