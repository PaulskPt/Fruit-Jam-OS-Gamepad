# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT
import atexit
import sys
import time

if "/apps/Metro_RP2350_Snake" not in sys.path:
    sys.path.append("/apps/Metro_RP2350_Snake")

from micropython import const
import supervisor
import displayio
import terminalio
from adafruit_display_text.text_box import TextBox
from adafruit_fruitjam.peripherals import request_display_config
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
    
from snake_helpers import World, Snake, GameOverException, SpeedAdjuster

# state machine constant
STATE_TITLE = const(0)
STATE_PLAYING = const(1)
STATE_PAUSED = const(2)
STATE_GAME_OVER = const(3)

# begin in the title state
CURRENT_STATE = STATE_TITLE

# movement key bindings (kept for optional keyboard fallback)
KEY_UP = "w"
KEY_LEFT = "a"
KEY_DOWN = "s"
KEY_RIGHT = "d"
KEY_PAUSE = "t"

# how many segments the snake will start with
INITIAL_SNAKE_LEN = 3

# variable for the players score
score = 0

request_display_config(320, 240)
display = supervisor.runtime.display

# initialize shared GamepadManager
pad = GamepadManager(check_bridge=False, debug=False)
if pad.connected:
    pad.print_controls("Snake", (
        ("D-Pad", "Move snake"),
        ("Start", "Pause / Resume"),
        ("A / Start", "Start / Play again"),
        ("B / Select", "Exit to launcher"),
    ))
    pad.wait_for_release(min_drain=0.25, timeout=1.5)


def atexit_callback():
    if pad is not None:
        pad.release()


atexit.register(atexit_callback)

# load title splash screen bitmap
title_bmp = displayio.OnDiskBitmap("snake_splash.bmp")
# create a tilegrid for the title splash screen
title_tg = displayio.TileGrid(bitmap=title_bmp, pixel_shader=title_bmp.pixel_shader)

instructions_txt = TextBox(
    terminalio.FONT,
    text="D-Pad: Move | Start: Pause\nPress A or Start to play",
    width=max(title_bmp.width, 220),
    height=32,
    align=TextBox.ALIGN_CENTER,
)
instructions_txt.anchor_point = (0.5, 0)
instructions_txt.anchored_position = (title_bmp.width // 2, title_bmp.height + 2)

# create a group for the title splash screen and put it in the center of the display
title_group = displayio.Group()
title_group.append(title_tg)
title_group.append(instructions_txt)
title_group.x = display.width // 2 - title_bmp.width // 2
title_group.y = display.height // 2 - title_bmp.height // 2 - 8

# initialize SpeedAdjuster to control how fast the snake is moving
speed_adjuster = SpeedAdjuster(12)

# initialize the world with enough room unused at the top for the score bar
world = World(height=28, width=40)
# move the world down to make room for the score bar
world.y = 16

# initialize a Snake instance and grow it to the appropriate size
snake = Snake(starting_location=[10, 10])
for i in range(INITIAL_SNAKE_LEN - 1):
    snake.grow()

# add one of each type of apple to the world
world.add_apple(snake=snake, apple_sprite_index=World.APPLE_RED_SPRITE_INDEX)
world.add_apple(snake=snake, apple_sprite_index=World.APPLE_GREEN_SPRITE_INDEX)

# create a group to hold everything for the game
game_group = displayio.Group()

# add the world to the game group
game_group.append(world)

# create TextBox to hold the score in a bar at the top of the display
score_txt = TextBox(
    terminalio.FONT, text=f"Score: {score}", color=0xFFFFFF, width=320, height=16
)
score_txt.anchor_point = (0, 0)
score_txt.anchored_position = (0, 2)

# add the score text to the game group
game_group.append(score_txt)

# create a TextBox to hold the game over message
game_over_label = TextBox(
    terminalio.FONT,
    text="",
    color=0xFFFFFF,
    background_color=0x000000,
    width=200,
    height=80,
    align=TextBox.ALIGN_CENTER,
)
# move it to the center of the display
game_over_label.anchor_point = (0, 0)
game_over_label.anchored_position = (
    display.width // 2 - game_over_label.width // 2,
    40,
)

# make it hidden, we'll show it when the game is over.
game_over_label.hidden = True

# add it to the game group
game_group.append(game_over_label)

# set the title group to show on the display
display.root_group = title_group

# draw the snake in its starting location
world.draw_snake(snake)

# timestamp of the game step render
prev_step_time = time.monotonic()

# variable to hold string read from the keyboard to get button presses
cur_btn_val = None

while True:
    # current timestamp
    now = time.monotonic()

    # poll shared GamepadManager
    if pad is not None and pad.connected:
        pad.update()

    # check if there is any keyboard input
    available = supervisor.runtime.serial_bytes_available

    # if there is some keyboard input
    if available:
        cur_btn_val = sys.stdin.read(available).lower()
    else:
        cur_btn_val = None

    # if the current state is title screen
    if CURRENT_STATE == STATE_TITLE:
        start_pressed = (
            cur_btn_val is not None
            or (
                pad is not None
                and pad.connected
                and (
                    pad.is_any_just_pressed(A_BUTTONS)
                    or pad.is_any_just_pressed(START_BUTTONS)
                )
            )
        )
        if start_pressed:
            display.root_group = game_group
            CURRENT_STATE = STATE_PLAYING

    # if game is being played
    elif CURRENT_STATE == STATE_PLAYING:
        # up input
        if cur_btn_val == KEY_UP or (
            pad is not None and pad.connected and pad.is_any_just_pressed(UP_BUTTONS)
        ):
            if snake.direction not in (snake.DIRECTION_DOWN, snake.DIRECTION_UP):
                snake.direction = snake.DIRECTION_UP

        # down input
        if cur_btn_val == KEY_DOWN or (
            pad is not None and pad.connected and pad.is_any_just_pressed(DOWN_BUTTONS)
        ):
            if snake.direction not in (snake.DIRECTION_DOWN, snake.DIRECTION_UP):
                snake.direction = snake.DIRECTION_DOWN

        # right input
        if cur_btn_val == KEY_RIGHT or (
            pad is not None and pad.connected and pad.is_any_just_pressed(RIGHT_BUTTONS)
        ):
            if snake.direction not in (snake.DIRECTION_LEFT, snake.DIRECTION_RIGHT):
                snake.direction = snake.DIRECTION_RIGHT

        # left input
        if cur_btn_val == KEY_LEFT or (
            pad is not None and pad.connected and pad.is_any_just_pressed(LEFT_BUTTONS)
        ):
            if snake.direction not in (snake.DIRECTION_LEFT, snake.DIRECTION_RIGHT):
                snake.direction = snake.DIRECTION_LEFT

        # pause input
        if cur_btn_val == KEY_PAUSE or (
            pad is not None and pad.connected and pad.is_any_just_pressed(START_BUTTONS)
        ):
            CURRENT_STATE = STATE_PAUSED

        # if it's time to render a step of the game
        if now >= prev_step_time + speed_adjuster.delay:
            try:
                result = world.move_snake(snake)

                if result == World.APPLE_RED_SPRITE_INDEX:
                    speed_adjuster.decrease_speed()
                    score += ((20 - speed_adjuster.speed) // 3) + snake.size
                    score_txt.text = f"Score: {score}"

                elif result == World.APPLE_GREEN_SPRITE_INDEX:
                    speed_adjuster.increase_speed()
                    score += ((20 - speed_adjuster.speed) // 3) + 3 + snake.size
                    score_txt.text = f"Score: {score}"

            except GameOverException:
                output_str = (
                    f"Game Over\nScore: {score}\nA / Start: Play Again\nB / Select: Quit"
                )
                game_over_label.text = output_str
                game_over_label.hidden = False
                CURRENT_STATE = STATE_GAME_OVER

            prev_step_time = now

    # if the game is paused
    elif CURRENT_STATE == STATE_PAUSED:
        if cur_btn_val == KEY_PAUSE or (
            pad is not None and pad.connected and pad.is_any_just_pressed(START_BUTTONS)
        ):
            CURRENT_STATE = STATE_PLAYING

    # if the current state is game over
    elif CURRENT_STATE == STATE_GAME_OVER:
        # play again if P, A, or Start is pressed
        if cur_btn_val == "p" or (
            pad is not None
            and pad.connected
            and (
                pad.is_any_just_pressed(A_BUTTONS)
                or pad.is_any_just_pressed(START_BUTTONS)
            )
        ):
            if pad is not None:
                pad.release()
            supervisor.set_next_code_file(__file__)
            supervisor.reload()

        # exit to Fruit Jam OS menu if Q, B, or Select is pressed
        if cur_btn_val == "q" or (
            pad is not None
            and pad.connected
            and (
                pad.is_any_just_pressed(B_BUTTONS)
                or pad.is_any_just_pressed(SELECT_BUTTONS)
            )
        ):
            if pad is not None:
                pad.release()
            supervisor.reload()
