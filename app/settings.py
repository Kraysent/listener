import enum
import json
import pathlib
from pynput import keyboard
import pydantic


class Hotkey(enum.Enum):
    F4 = "f4"
    RIGHT_OPTION = "right_option"

    def to_keyboard_key(self) -> keyboard.Key | keyboard.KeyCode:
        if self == Hotkey.F4:
            return keyboard.Key.f4
        elif self == Hotkey.RIGHT_OPTION:
            return keyboard.Key.alt_r
        else:
            raise ValueError(f"Unknown hotkey: {self}")

    def to_string(self) -> str:
        if self == Hotkey.F4:
            return "F4"
        elif self == Hotkey.RIGHT_OPTION:
            return "Right Option"
        else:
            raise ValueError(f"Unknown hotkey: {self}")


class Settings(pydantic.BaseModel):
    hotkey: Hotkey
    whisper_model: str
    sample_rate: int


def load_settings(config_path: pathlib.Path):
    with open(config_path, "r", encoding="utf-8") as f:
        data = f.read()
    settings_dict = json.loads(data)
    return Settings(**settings_dict)
