# SPDX-FileCopyrightText: 2025 Melissa LeBlanc-Williams
#
# SPDX-License-Identifier: MIT
# Adapted for use with a SNES-type gamepad controller by Paulus Schulinck (Github @Paulskpt) and Gemini (Google AI)
import atexit
import gc
import json
import sys
import time
import board
import supervisor
import audiobusio
import displayio
import adafruit_pathlib as pathlib
import adafruit_fruitjam.Peripherals

APP_DIR = "/".join(__file__.split("/")[:-1])
if APP_DIR and APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

from audio import Audio  # pylint: disable=wrong-import-position
from game import Game  # pylint: disable=wrong-import-position
from definitions import SECOND_LENGTH, TICKS_PER_SECOND  # pylint: disable=wrong-import-position

# Change this to use a different data file
DATA_FILE = "CHIPS.DAT"

SOUND_EFFECTS = {
    "BUTTON_PUSHED": "sounds/pop2.wav",
    "DOOR_OPENED": "sounds/door.wav",
    "ITEM_COLLECTED": "sounds/blip2.wav",
    "BOOTS_STOLEN": "sounds/strike.wav",
    "WATER_SPLASH": "sounds/water2.wav",
    "TELEPORT": "sounds/teleport.wav",
    "CANT_MOVE": "sounds/oof3.wav",
    "CHIP_LOSES": "sounds/bummer.wav",
    "LEVEL_COMPLETE": "sounds/ditty1.wav",
    "IC_COLLECTED": "sounds/click3.wav",
    "BOMB_EXPLOSION": "sounds/hit3.wav",
    "SOCKET_SOUND": "sounds/chimes.wav",
    "TIME_LOW_TICK": "sounds/click1.wav",
    "TIME_UP": "sounds/bell.wav",
}

launcher_config = {}
for directory in ("/", "/sd/", "/saves/"):
    launcher_config_path = directory + "launcher.conf.json"
    if pathlib.Path(launcher_config_path).exists():
        with open(launcher_config_path, "r") as f:
            launcher_config = launcher_config | json.load(f)
if "audio" not in launcher_config:
    launcher_config["audio"] = {}

fjPeriphs = adafruit_fruitjam.Peripherals.Peripherals(
    audio_output=launcher_config["audio"].get("output", "headphone"),
    safe_volume_limit=launcher_config["audio"].get("volume_override_danger", 0.75),
    sample_rate=44100,
    bit_depth=16,
    i2c=board.I2C(),
)
if (
    not hasattr(board, "I2S_BCLK")
    and hasattr(board, "D9")
    and hasattr(board, "D10")
    and hasattr(board, "D11")
):
    fjPeriphs.audio = audiobusio.I2SOut(board.D9, board.D10, board.D11)

if "volume" in launcher_config["audio"]:
    fjPeriphs.volume = launcher_config["audio"]["volume"]

if fjPeriphs.audio is not None:
    audio = Audio(fjPeriphs.audio, SOUND_EFFECTS)
else:
    audio = None

adafruit_fruitjam.Peripherals.request_display_config(320, 240, 8)

game = Game(supervisor.runtime.display, DATA_FILE, audio)


def atexit_callback():
    if hasattr(game, "_keyboard") and game._keyboard is not None:
        game._keyboard.release()
    try:
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception:
        pass
    try:
        supervisor.runtime.display.root_group = displayio.Group()
        gc.collect()
    except Exception:
        pass
    supervisor.set_next_code_file(
        "/code.py",
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/",
    )


atexit.register(atexit_callback)

tick_length = SECOND_LENGTH / 1000 / TICKS_PER_SECOND
try:
    while True:
        start = time.monotonic()
        game.tick()
        while time.monotonic() - start < tick_length:
            pass
except SystemExit:
    supervisor.reload()
