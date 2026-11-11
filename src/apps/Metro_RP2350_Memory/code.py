# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
An implementation of the card game memory.
Adapted for Fruit Jam OS with shared /lib/fj_gamepad.py SNES gamepad support.
"""
import sys
import random
import time
import gc
import atexit
from displayio import Group, OnDiskBitmap, TileGrid
from adafruit_display_text.bitmap_label import Label
from adafruit_display_text.text_box import TextBox
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
from adafruit_ticks import ticks_ms
import supervisor
import terminalio
from adafruit_fruitjam.peripherals import request_display_config
from adafruit_usb_host_mouse import find_and_init_boot_mouse, find_and_init_report_mouse
from adafruit_pathlib import Path
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    DOWN_BUTTONS,
    LEFT_BUTTONS,
    RIGHT_BUTTONS,
    A_BUTTONS,
    B_BUTTONS,
    START_BUTTONS,
    SELECT_BUTTONS,
)


def random_selection(lst, count):
    if len(lst) <= count:
        raise ValueError("Count must be less than or equal to length of list")
    iter_copy = list(lst)
    selection = set()
    while len(selection) < count:
        selection.add(iter_copy.pop(random.randrange(len(iter_copy))))
    return list(selection)


def update_score_text():
    for _ in range(2):
        out_str = f"p{_ + 1} score: {player_scores[_]}"
        score_lbls[_].text = out_str


# state machine constants
STATE_TITLE = 0
STATE_PLAYING = 1
STATE_GAMEOVER = 2
CUR_STATE = STATE_TITLE

launcher_config = LauncherConfig()
my_debug = launcher_config.data.get("my_debug", False)
use_mouse = launcher_config.data.get("use_mouse", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)

request_display_config(320, 240)
display = supervisor.runtime.display

# Initialize shared GamepadManager
pad = None
if use_gamepad:
    pad = GamepadManager(check_bridge=False, debug=my_debug)
    if pad.connected:
        pad.print_controls("Memory", (
            ("D-Pad", "Move cursor"),
            ("A / B", "Start / Flip card"),
            ("A / START", "Play again (Game Over)"),
            ("START / SELECT", "Exit to launcher"),
        ))
        pad.wait_for_release(min_drain=0.25, timeout=1.5)

main_group = Group()
display.root_group = main_group

score_lbls = []
colors = [0xFF00FF, 0x00FF00]
current_turn_index = random.randrange(0, 2)
cards_flipped_this_turn = []
player_scores = [0, 0]
grid_size = (6, 4)

card_grid = GridLayout(x=10, y=10, width=260, height=200, grid_size=grid_size)

CARD_FRONT_SPRITE_INDEXES = {1, 2, 3, 4, 5, 6, 7, 9}
pool = list(CARD_FRONT_SPRITE_INDEXES) + list(CARD_FRONT_SPRITE_INDEXES)
duplicates = random_selection(CARD_FRONT_SPRITE_INDEXES, 4)
pool += duplicates + duplicates

card_locations = []
sprites = OnDiskBitmap("memory_game_sprites.bmp")
card_tgs = []

for y in range(4):
    for x in range(6):
        new_tg = TileGrid(
            bitmap=sprites,
            default_tile=10,
            tile_height=32,
            tile_width=32,
            height=1,
            width=1,
            pixel_shader=sprites.pixel_shader,
        )
        card_tgs.append(new_tg)
        card_grid.add_content(new_tg, grid_position=(x, y), cell_size=(1, 1))
        random_choice = random.randrange(0, len(pool) - 1) if len(pool) > 1 else 0
        card_locations.append(pool.pop(random_choice))

card_grid.x = display.width // 2 - card_grid.width // 2
card_grid.y = display.height - card_grid.height
main_group.append(card_grid)

game_over_group = Group()
game_over_label = TextBox(
    terminalio.FONT,
    text="",
    color=0xFFFFFF,
    background_color=0x222222,
    width=display.width // 2,
    height=80,
    align=TextBox.ALIGN_CENTER,
)
game_over_label.anchor_point = (0, 0)
game_over_label.anchored_position = (
    display.width // 2 - game_over_label.width // 2,
    40,
)
game_over_group.hidden = True
game_over_group.append(game_over_label)

play_again_btn_bmp = OnDiskBitmap("btn_play_again.bmp")
exit_btn_bmp = OnDiskBitmap("btn_exit.bmp")

play_again_btn = TileGrid(
    bitmap=play_again_btn_bmp, pixel_shader=play_again_btn_bmp.pixel_shader
)
play_again_btn_bmp.pixel_shader.make_transparent(0)
play_again_btn.x = display.width // 2 - play_again_btn_bmp.width // 2 - 30
play_again_btn.y = 80

exit_btn = TileGrid(bitmap=exit_btn_bmp, pixel_shader=exit_btn_bmp.pixel_shader)
exit_btn_bmp.pixel_shader.make_transparent(0)
exit_btn.x = display.width // 2 - exit_btn_bmp.width // 2 + 30
exit_btn.y = 80

game_over_group.append(play_again_btn)
game_over_group.append(exit_btn)
main_group.append(game_over_group)

exit_game = TextBox(
    terminalio.FONT,
    text="Exit",
    color=0xFFFFFF,
    background_color=0xFF0000,
    width=30,
    height=15,
    align=TextBox.ALIGN_CENTER,
)
exit_game.x = display.width - 30
exit_game.y = display.height - 15
main_group.append(exit_game)

for i in range(2):
    score_lbl = Label(terminalio.FONT, text="", color=colors[i], scale=1)
    if i == 0:
        score_lbl.anchor_point = (0, 0)
        score_lbl.anchored_position = (4, 1)
    else:
        score_lbl.anchor_point = (1.0, 0)
        score_lbl.anchored_position = (display.width - 4, 1)
    score_lbls.append(score_lbl)
    main_group.append(score_lbl)

update_score_text()

current_player_lbl = Label(
    terminalio.FONT, text="Current Player", color=colors[current_turn_index], scale=1
)
current_player_lbl.anchor_point = (0.5, 0)
current_player_lbl.anchored_position = (display.width // 2, 1)
main_group.append(current_player_lbl)

title_screen_bmp = OnDiskBitmap("memory_title.bmp")
title_screen_tg = TileGrid(
    bitmap=title_screen_bmp, pixel_shader=title_screen_bmp.pixel_shader
)
main_group.append(title_screen_tg)

# Initialize optional USB mouse or standalone cursor TileGrid for gamepad
mouse_ptr = None
if use_mouse:
    mouse_ptr = find_and_init_boot_mouse("mouse_cursor.bmp")
    if mouse_ptr is None:
        mouse_ptr = find_and_init_report_mouse("mouse_cursor.bmp")

if mouse_ptr is not None:
    cursor_tg = mouse_ptr.tilegrid
else:
    cursor_bmp = OnDiskBitmap("mouse_cursor.bmp")
    cursor_bmp.pixel_shader.make_transparent(0)
    cursor_tg = TileGrid(cursor_bmp, pixel_shader=cursor_bmp.pixel_shader)

cursor_x = float(display.width // 2)
cursor_y = float(display.height // 2)
cursor_tg.x = int(cursor_x)
cursor_tg.y = int(cursor_y)
main_group.append(cursor_tg)

def exit_to_launcher():
    if pad is not None:
        pad.release()
    supervisor.set_next_code_file("/code.py", working_directory="/")
    supervisor.reload()


def atexit_callback():
    if pad is not None:
        pad.release()
    if mouse_ptr is not None and mouse_ptr.device is not None:
        try:
            mouse_ptr.release()
            if mouse_ptr.was_attached:
                while supervisor.runtime.serial_bytes_available:
                    sys.stdin.read(1)
        except Exception:
            pass
    try:
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception:
        pass
    try:
        display.root_group = Group()
        gc.collect()
    except Exception:
        pass


atexit.register(atexit_callback)

WAIT_UNTIL = 0
waiting_to_reset = False
last_left_button_state = 0
CURSOR_SPEED = 4.0
ACTION_BTNS = A_BUTTONS + B_BUTTONS

while True:
    now = ticks_ms()
    left_button_pressed = False

    # Poll SNES Gamepad
    if pad is not None and pad.connected:
        pad.update()

        if CUR_STATE in (STATE_TITLE, STATE_PLAYING):
            if pad.is_any_just_pressed(START_BUTTONS):
                exit_to_launcher()

            if pad.is_any_held(LEFT_BUTTONS):
                cursor_x = max(0.0, cursor_x - CURSOR_SPEED)
            if pad.is_any_held(RIGHT_BUTTONS):
                cursor_x = min(float(display.width - 1), cursor_x + CURSOR_SPEED)
            if pad.is_any_held(UP_BUTTONS):
                cursor_y = max(0.0, cursor_y - CURSOR_SPEED)
            if pad.is_any_held(DOWN_BUTTONS):
                cursor_y = min(float(display.height - 1), cursor_y + CURSOR_SPEED)

            cursor_tg.x = int(cursor_x)
            cursor_tg.y = int(cursor_y)

            if pad.is_any_just_pressed(ACTION_BTNS):
                left_button_pressed = True

        elif CUR_STATE == STATE_GAMEOVER:
            if pad.is_any_just_pressed(A_BUTTONS) or pad.is_any_just_pressed(START_BUTTONS):
                if pad is not None:
                    pad.release()
                supervisor.set_next_code_file(
                    __file__,
                    working_directory=Path(__file__).parent.absolute(),
                )
                supervisor.reload()
            elif pad.is_any_just_pressed(B_BUTTONS) or pad.is_any_just_pressed(SELECT_BUTTONS):
                exit_to_launcher()

    # Poll optional USB mouse
    if mouse_ptr is not None:
        buttons = mouse_ptr.update()
        current_left_button_state = 1 if (buttons and "left" in buttons) else 0
        if current_left_button_state == 1 and last_left_button_state == 0:
            left_button_pressed = True
        last_left_button_state = current_left_button_state
        cursor_x = float(cursor_tg.x)
        cursor_y = float(cursor_tg.y)

    # Title screen state
    if CUR_STATE == STATE_TITLE:
        if left_button_pressed:
            CUR_STATE = STATE_PLAYING
            title_screen_tg.hidden = True
            cursor_tg.pixel_shader[2] = colors[current_turn_index]

    # Playing state
    elif CUR_STATE == STATE_PLAYING:
        if waiting_to_reset and now >= WAIT_UNTIL:
            waiting_to_reset = False

            if (
                card_tgs[cards_flipped_this_turn[0]][0]
                == card_tgs[cards_flipped_this_turn[1]][0]
            ):
                card_tgs[cards_flipped_this_turn[0]][0] = 8
                card_tgs[cards_flipped_this_turn[1]][0] = 8
                player_scores[current_turn_index] += 1
                update_score_text()

                if (
                    player_scores[0] + player_scores[1]
                    >= (grid_size[0] * grid_size[1]) // 2
                ):
                    if player_scores[0] == player_scores[1]:
                        game_over_label.text = "Game Over\nTie Game"
                    elif player_scores[0] < player_scores[1]:
                        game_over_label.text = "Game Over\nPlayer 2 Wins"
                        game_over_label.color = colors[1]
                    else:
                        game_over_label.text = "Game Over\nPlayer 1 Wins"
                        game_over_label.color = colors[0]

                    game_over_group.hidden = False
                    CUR_STATE = STATE_GAMEOVER
            else:
                card_tgs[cards_flipped_this_turn[0]][0] = 10
                card_tgs[cards_flipped_this_turn[1]][0] = 10
                current_turn_index = (current_turn_index + 1) % 2
                current_player_lbl.color = colors[current_turn_index]
                cursor_tg.pixel_shader[2] = colors[current_turn_index]

            cards_flipped_this_turn = []

        if now >= WAIT_UNTIL and left_button_pressed:
            if cursor_tg.x >= display.width - 30 and cursor_tg.y >= display.height - 20:
                exit_to_launcher()

            for card_index, card in enumerate(card_tgs):
                coords = (cursor_tg.x - card_grid.x, cursor_tg.y - card_grid.y, 0)
                if card[0] == 10 and card.contains(coords):
                    card[0] = card_locations[card_tgs.index(card)]
                    cards_flipped_this_turn.append(card_index)

                    if len(cards_flipped_this_turn) == 2:
                        WAIT_UNTIL = ticks_ms() + 1500
                        waiting_to_reset = True

    # Game Over state (pointer click fallback)
    elif CUR_STATE == STATE_GAMEOVER:
        if left_button_pressed:
            coords = (cursor_tg.x, cursor_tg.y, 0)
            if play_again_btn.contains(coords):
                if pad is not None:
                    pad.release()
                supervisor.set_next_code_file(
                    __file__,
                    working_directory=Path(__file__).parent.absolute(),
                )
                supervisor.reload()
            elif exit_btn.contains(coords):
                exit_to_launcher()

    time.sleep(0.016)
