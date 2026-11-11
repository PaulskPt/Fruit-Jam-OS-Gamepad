# SPDX-FileCopyrightText: 2025 Melissa LeBlanc-Williams for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
An implementation of minesweeper. The logic game where the player
correctly identifies the locations of mines on a grid by clicking on squares
and revealing the number of mines in adjacent squares.

The player can also flag squares they suspect contain mines. The game ends when
the player successfully reveals all squares without mines or clicks on a mine.
"""
import array
import atexit
import gc
import sys
import time
from displayio import Group, OnDiskBitmap, TileGrid, Bitmap, Palette
from adafruit_display_text.bitmap_label import Label
from adafruit_display_text.text_box import TextBox
from adafruit_fruitjam.peripherals import request_display_config
import supervisor
import terminalio
from adafruit_usb_host_mouse import find_and_init_boot_mouse
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    DOWN_BUTTONS,
    LEFT_BUTTONS,
    RIGHT_BUTTONS,
    A_BUTTONS,
    B_BUTTONS,
    X_BUTTONS,
    Y_BUTTONS,
    START_BUTTONS,
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
)

# Ensure local app modules (gamelogic.py, menu.py, eventbutton.py) are importable
APP_DIR = "/".join(__file__.split("/")[:-1])
if APP_DIR and APP_DIR not in sys.path:
    sys.path.append(APP_DIR)

from eventbutton import EventButton  # pylint: disable=wrong-import-position
from gamelogic import GameLogic, BLANK, INFO_BAR_HEIGHT, DIFFICULTIES  # pylint: disable=wrong-import-position
from menu import Menu, SubMenu  # pylint: disable=wrong-import-position

launcher_config = LauncherConfig()
my_debug = launcher_config.data.get("my_debug", False)
use_mouse = launcher_config.data.get("use_mouse", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)

# Initialize display (keep standard 320x240 HSTX resolution)
if hasattr(supervisor.runtime, "display") and supervisor.runtime.display is not None:
    request_display_config(320, 240)
    display = supervisor.runtime.display
else:
    from displayio import release_displays
    import picodvi
    import board
    import framebufferio

    release_displays()
    fb = picodvi.Framebuffer(
        320,
        240,
        clk_dp=board.CKP,
        clk_dn=board.CKN,
        red_dp=board.D0P,
        red_dn=board.D0N,
        green_dp=board.D1P,
        green_dn=board.D1N,
        blue_dp=board.D2P,
        blue_dn=board.D2N,
        color_depth=16,
    )
    display = framebufferio.FramebufferDisplay(fb)
    supervisor.runtime.display = display

# Initialize shared GamepadManager
pad = None
if use_gamepad:
    pad = GamepadManager(check_bridge=False, debug=my_debug)
    if pad.connected:
        pad.print_controls("Minesweeper", (
            ("D-Pad", "Move cursor"),
            ("A", "Reveal / Select menu"),
            ("B", "Flag / Unflag square"),
            ("X", "Chord square"),
            ("Y", "Reset game"),
            ("L1 / R1", "Change difficulty"),
            ("START", "Exit to launcher"),
        ))
        pad.wait_for_release(min_drain=0.25, timeout=1.5)

game_logic = GameLogic(display)  # pylint: disable=no-value-for-parameter

# Load the spritesheet
sprite_sheet = OnDiskBitmap("bitmaps/game_sprites.bmp")

# Main group will hold all the visual layers
main_group = Group()
display.root_group = main_group

# Add Background to the Main Group
background = Bitmap(display.width, display.height, 1)
bg_color = Palette(1)
bg_color[0] = 0xAAAAAA
main_group.append(TileGrid(background, pixel_shader=bg_color))

# Add Game group, which holds the game board, to the main group
game_group = Group()
main_group.append(game_group)

# Add a group for the UI Elements
ui_group = Group()
main_group.append(ui_group)

MENU_ITEM_HEIGHT = INFO_BAR_HEIGHT


def create_game_board():
    if len(game_group) > 0:
        game_group.pop()

    x = display.width // 2 - (game_logic.grid_width * 16) // 2
    y = (
        (display.height - INFO_BAR_HEIGHT) // 2
        - (game_logic.grid_height * 16) // 2
        + INFO_BAR_HEIGHT
    )

    game_board = TileGrid(
        sprite_sheet,
        pixel_shader=sprite_sheet.pixel_shader,
        width=game_logic.grid_width,
        height=game_logic.grid_height,
        tile_height=16,
        tile_width=16,
        x=x,
        y=y,
        default_tile=BLANK,
    )

    game_group.append(game_board)
    return game_board


def update_ui():
    mines_left_label.text = f"Mines: {game_logic.mines_left}"
    elapsed_time_label.text = f"Time: {game_logic.elapsed_time}"


# Initialize optional USB mouse, or create standalone cursor TileGrid for gamepad
mouse = None
if use_mouse:
    mouse = find_and_init_boot_mouse(cursor_image="bitmaps/mouse_cursor.bmp")

if mouse is not None:
    mouse.sensitivity = 4
    cursor_tg = mouse.tilegrid
else:
    cursor_bmp = OnDiskBitmap("bitmaps/mouse_cursor.bmp")
    cursor_bmp.pixel_shader.make_transparent(0)
    cursor_tg = TileGrid(cursor_bmp, pixel_shader=cursor_bmp.pixel_shader)

cursor_x = float(display.width // 2)
cursor_y = float(display.height // 2)
cursor_tg.x = int(cursor_x)
cursor_tg.y = int(cursor_y)
main_group.append(cursor_tg)

buf = array.array("b", [0] * 4)
waiting_for_release = False
chord_selected = False
chord_coords = (0, 0)
left_button = right_button = False
mouse_coords = (int(cursor_x), int(cursor_y))

# Create the UI Elements (Ideally fit into 320x16 area)
mines_left_label = Label(
    terminalio.FONT,
    color=0x000000,
    x=5,
    y=0,
)
mines_left_label.anchor_point = (0, 0)
mines_left_label.anchored_position = (5, 2)
ui_group.append(mines_left_label)

elapsed_time_label = Label(
    terminalio.FONT,
    color=0x000000,
    x=display.width - 50,
    y=0,
)
elapsed_time_label.anchor_point = (1, 0)
elapsed_time_label.anchored_position = (display.width - 5, 2)
ui_group.append(elapsed_time_label)

difficulty_menu = SubMenu(
    "Difficulty",
    70,
    80,
    display.width // 2 - 70,
    0,
)

reset_menu = SubMenu(
    "Reset",
    50,
    40,
    display.width // 2 + 15,
    0,
)

message_dialog = Group()
message_dialog.hidden = True


def reset():
    game_logic.reset()
    game_logic.game_board = create_game_board()
    message_dialog.hidden = True


def set_difficulty(diff):
    game_logic.difficulty = diff
    reset()
    difficulty_menu.select_item(DIFFICULTIES[diff]["label"].lower().replace(" ", "_"))


def hide_group(group):
    group.hidden = True


for i, difficulty in enumerate(DIFFICULTIES):
    selected = i == game_logic.difficulty
    difficulty_menu.add_item((set_difficulty, i), difficulty["label"], selected)

reset_menu.add_item(reset, "OK")

menu = Menu()
menu.append(difficulty_menu)
menu.append(reset_menu)
ui_group.append(menu)

reset()

message_label = TextBox(
    terminalio.FONT,
    text="",
    color=0x333333,
    background_color=0xEEEEEE,
    width=display.width // 4,
    height=50,
    align=TextBox.ALIGN_CENTER,
    padding_top=5,
)
message_label.anchor_point = (0, 0)
message_label.anchored_position = (
    display.width // 2 - message_label.width // 2,
    display.height // 2 - message_label.height // 2,
)
message_dialog.append(message_label)

message_button = EventButton(
    (hide_group, message_dialog),
    label="OK",
    width=40,
    height=16,
    x=display.width // 2 - 20,
    y=display.height // 2 - message_label.height // 2 + 20,
    style=EventButton.RECT,
)
message_dialog.append(message_button)
ui_group.append(message_dialog)

menus = (reset_menu, difficulty_menu)
exit_to_launcher = False
CURSOR_SPEED = 4.0
# Filter out L1/R1 from left/right cursor movement so L1/R1 can switch difficulty
DPAD_LEFT = tuple(b for b in LEFT_BUTTONS if b not in SHOULDER_LEFT_BUTTONS)
DPAD_RIGHT = tuple(b for b in RIGHT_BUTTONS if b not in SHOULDER_RIGHT_BUTTONS)


def atexit_callback():
    global main_group
    if pad is not None:
        pad.release()
    if mouse is not None:
        try:
            mouse.release()
        except Exception:
            pass
    try:
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception:
        pass
    try:
        display.root_group = Group()
        main_group = None
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

# main loop
while True:
    update_ui()

    gp_left = 0
    gp_right = 0
    gp_chord = False

    # Poll SNES Gamepad
    if pad is not None and pad.connected:
        pad.update()

        if pad.is_any_just_pressed(START_BUTTONS):
            exit_to_launcher = True
            break

        if pad.is_any_just_pressed(Y_BUTTONS):
            reset()

        if pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS):
            new_diff = (game_logic.difficulty - 1) % len(DIFFICULTIES)
            set_difficulty(new_diff)

        if pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
            new_diff = (game_logic.difficulty + 1) % len(DIFFICULTIES)
            set_difficulty(new_diff)

        # Smooth D-Pad cursor movement
        if pad.is_any_held(DPAD_LEFT):
            cursor_x = max(0.0, cursor_x - CURSOR_SPEED)
        if pad.is_any_held(DPAD_RIGHT):
            cursor_x = min(float(display.width - 1), cursor_x + CURSOR_SPEED)
        if pad.is_any_held(UP_BUTTONS):
            cursor_y = max(0.0, cursor_y - CURSOR_SPEED)
        if pad.is_any_held(DOWN_BUTTONS):
            cursor_y = min(float(display.height - 1), cursor_y + CURSOR_SPEED)

        cursor_tg.x = int(cursor_x)
        cursor_tg.y = int(cursor_y)

        if pad.is_any_held(A_BUTTONS):
            gp_left = 1
        if pad.is_any_held(B_BUTTONS):
            gp_right = 1
        if pad.is_any_held(X_BUTTONS):
            gp_chord = True

    # Poll optional USB mouse
    m_left = 0
    m_right = 0
    if mouse is not None:
        mouse.update()
        buttons = mouse.pressed_btns
        if buttons:
            m_left = 1 if "left" in buttons else 0
            m_right = 1 if "right" in buttons else 0
        cursor_x = float(cursor_tg.x)
        cursor_y = float(cursor_tg.y)

    left_button = 1 if (gp_left or m_left or gp_chord) else 0
    right_button = 1 if (gp_right or m_right or gp_chord) else 0
    mouse_coords = (cursor_tg.x, cursor_tg.y)

    if waiting_for_release and not left_button and not right_button:
        waiting_for_release = False

    if not message_dialog.hidden:
        if message_button.handle_mouse(mouse_coords, left_button, waiting_for_release):
            waiting_for_release = True
        time.sleep(0.016)
        continue

    if menu.handle_mouse(mouse_coords, left_button, waiting_for_release):
        waiting_for_release = True
    else:
        ms_board = game_logic.game_board

        if left_button and right_button and not chord_selected:
            chord_coords = ((cursor_tg.x - ms_board.x) // 16, (cursor_tg.y - ms_board.y) // 16)
            chord_selected = game_logic.square_chord_highlight(chord_coords)
            if chord_selected:
                waiting_for_release = True

        if (
            ms_board.x <= cursor_tg.x < ms_board.x + game_logic.grid_width * 16
            and ms_board.y <= cursor_tg.y < ms_board.y + game_logic.grid_height * 16
            and not waiting_for_release
        ):
            coords = ((cursor_tg.x - ms_board.x) // 16, (cursor_tg.y - ms_board.y) // 16)
            if chord_selected:
                chord_selected = False
                game_logic.square_chord_highlight(chord_coords, False)
                game_logic.square_chorded(chord_coords)
            elif right_button:
                game_logic.square_flagged(coords)
            elif left_button:
                if not game_logic.square_clicked(coords):
                    message_label.text = "Game Over"
                    message_dialog.hidden = False
            if left_button or right_button:
                waiting_for_release = True

        status = game_logic.check_for_win()
        if status:
            message_label.text = "You win!"
            message_dialog.hidden = False
        if status is None:
            time.sleep(0.016)
            continue

    time.sleep(0.016)

if exit_to_launcher:
    supervisor.reload()
