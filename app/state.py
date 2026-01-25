import enum
from typing import Callable
from dataclasses import dataclass
import pathlib
import rumps

from app import settings


class State(enum.Enum):
    STARTUP = "startup"
    READY_TO_LISTEN = "ready_to_listen"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    ERROR = "error"


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
    def __init__(self, config_path: pathlib.Path, on_quit: Callable[[], None]):
        super().__init__(
            "Listener",
            "🎤",
            menu=[rumps.MenuItem(_STATE_CONFIG[State.STARTUP].status)],
            quit_button=None,
        )

        self.config_path = config_path
        self.settings = settings.load_settings(config_path=config_path)
        self.on_quit_callback = on_quit
        self._settings_observers: list[Callable[[settings.Settings], None]] = []
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

    def subscribe_to_settings(
        self, callback: Callable[[settings.Settings], None]
    ) -> Callable[[], None]:
        self._settings_observers.append(callback)

        def unsubscribe() -> None:
            if callback in self._settings_observers:
                self._settings_observers.remove(callback)

        return unsubscribe

    def update_settings(self, new_settings: settings.Settings) -> None:
        self.settings = new_settings
        self._notify_settings_observers()

    def reload_settings(self) -> None:
        self.settings = settings.load_settings(config_path=self.config_path)
        self._notify_settings_observers()

    def _notify_settings_observers(self) -> None:
        for observer in self._settings_observers:
            observer(self.settings)

    def _quit_handler(self, _) -> None:
        self.on_quit_callback()
        rumps.quit_application()
