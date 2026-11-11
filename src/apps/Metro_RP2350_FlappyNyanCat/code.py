# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT
"""
A game featuring Nyan cat inspired by flappy bird.
Adapted for Fruit Jam OS with shared /lib/fj_gamepad.py SNES gamepad support.
by Paulus Schulinck (Github @PaulskPt) and Gemini (Google AI)
"""
import atexit
import gc
import random
import sys
import time
import terminalio
from displayio import Group, TileGrid, Bitmap, Palette
import supervisor
import bitmaptools
from adafruit_display_text.bitmap_label import Label
from micropython import const
import adafruit_imageload
from adafruit_fruitjam.peripherals import request_display_config
from adafruit_pathlib import Path
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    A_BUTTONS,
    B_BUTTONS,
    X_BUTTONS,
    Y_BUTTONS,
    START_BUTTONS,
    SELECT_BUTTONS,
)

# how strong the gravity is
FALL_SPEED = 0.35 # Was: 1

# how powerful the jump is
JUMP_SPEED = 2.5 # Was: 5

# maximum gravity speed
TERMINAL_VELOCITY = 3.5 # Was: 7

# make "close calls" more likely by fudging the collision check
COLLIDE_FUDGE_FACTOR = 8

# how many scaled pixels wide the trail will be
TRAIL_LENGTH = 10 # Wasa: 20

# current score
score = 0

request_display_config(320, 240)
display = supervisor.runtime.display

# initialize shared GamepadManager
pad = GamepadManager(check_bridge=False, debug=False)
if pad.connected:
    pad.print_controls("Flappy Nyan Cat", (
        ("A / B / Up", "Jump / Start"),
        ("X / Y", "Switch trail"),
        ("A / START", "Play again (Game Over)"),
        ("B / SELECT", "Quit to launcher"),
    ))
    pad.wait_for_release(min_drain=0.25, timeout=1.5)


def atexit_callback():
    if pad is not None:
        pad.release()
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

# initialize groups to hold visual elements
main_group = Group()

# any elements in this Group will be scaled up 2x
scaled_group = Group(scale=2)
main_group.append(scaled_group)


class Post(Group):
    GAP_TOP = const(0)
    GAP_MID = const(1)
    GAP_BOTTOM = const(2)

    def __init__(self, spritesheet, gap_location=GAP_MID):
        super().__init__()
        self.hidden = True
        self.sprites = spritesheet

        if gap_location == Post.GAP_MID:
            top_height = 4
            bottom_height = 4
        elif gap_location == Post.GAP_BOTTOM:
            top_height = 7
            bottom_height = 1
        elif gap_location == Post.GAP_TOP:
            top_height = 1
            bottom_height = 7
        else:
            raise ValueError("Invalid gap_location")

        self.top_post = TileGrid(
            post_sprites,
            pixel_shader=post_sprites_pixel_shader,
            height=top_height,
            width=1,
            tile_width=16,
            tile_height=16,
            default_tile=3,
        )

        for i in range(top_height):
            self.top_post[0, i] = 2 if i == top_height - 1 else 1

        self.bottom_post = TileGrid(
            post_sprites,
            pixel_shader=post_sprites_pixel_shader,
            height=bottom_height,
            width=1,
            tile_width=16,
            tile_height=16,
            default_tile=3,
        )

        for i in range(bottom_height):
            self.bottom_post[0, i] = 0 if i == 0 else 1

        self.bottom_post.y = 240 - bottom_height * 16

        self.append(self.top_post)
        self.append(self.bottom_post)

    def check_collision(self, sprite):
        if (
            (sprite.x * 2) - self.top_post.tile_width
            <= self.x
            <= (sprite.x * 2) + (sprite.tile_width * 2)
        ):
            if (
                sprite.y * 2
            ) + COLLIDE_FUDGE_FACTOR <= self.top_post.tile_height * self.top_post.height or (
                sprite.y * 2
            ) - COLLIDE_FUDGE_FACTOR >= self.bottom_post.y - (
                sprite.tile_height * 2
            ):
                return True

        return False


class PostPool:
    def __init__(self):
        self.pool = [
            Post(post_sprites, Post.GAP_MID),
            Post(post_sprites, Post.GAP_MID),
            Post(post_sprites, Post.GAP_BOTTOM),
            Post(post_sprites, Post.GAP_BOTTOM),
            Post(post_sprites, Post.GAP_TOP),
            Post(post_sprites, Post.GAP_TOP),
        ]

    def get_post(self, index=None):
        rnd_idx = random.randint(0, len(self.pool) - 1) if index is None else index
        next_post = self.pool.pop(rnd_idx)
        next_post.hidden = False
        return next_post

    def recycle_post(self, post):
        post.hidden = True
        self.pool.append(post)


class GameOverException(Exception):
    def __init__(self, msg):
        self.msg = msg
        super().__init__(self.msg)

# palette of colors for the trail
trail_palette = Palette(10)
trail_palette[0] = 0x000000
trail_palette[1] = 0xE71C1F
trail_palette[2] = 0xF39816
trail_palette[3] = 0xF1E610
trail_palette[4] = 0x6DB52F
trail_palette[5] = 0x428CCB
trail_palette[6] = 0x4B4C9C
trail_palette[7] = 0xF5ABB9
trail_palette[8] = 0x5BCFFA
trail_palette[9] = 0xFFFFFF
trail_palette.make_transparent(0)

trail_bmp = Bitmap(1, 6, 7)
for _i in range(6):
    trail_bmp[0, _i] = _i + 1

bg_bmp = Bitmap(16, 12, 1)
bg_palette = Palette(1)
bg_palette[0] = 0x00014F
bg_tilegrid = TileGrid(bg_bmp, pixel_shader=bg_palette)
bg_group = Group(scale=10)
bg_group.append(bg_tilegrid)
scaled_group.append(bg_group)

post_sprites, post_sprites_pixel_shader = adafruit_imageload.load("scratch_post_sprites.bmp")
post_sprites_pixel_shader.make_transparent(0)

post_pool = PostPool()
for _post in post_pool.pool:
    main_group.append(_post)

first_post = post_pool.get_post()
first_post.x = 320 - 16

second_post = post_pool.get_post(0)
second_post.x = 160

canvas_group = Group(scale=2)
trail_canvas_bmp = Bitmap(display.width // 4, display.height // 4, 10)
trail_canvas_tg = TileGrid(trail_canvas_bmp, pixel_shader=trail_palette)
canvas_group.append(trail_canvas_tg)
scaled_group.append(canvas_group)

nyan_bmp, nyan_bmp_pixel_shader = adafruit_imageload.load("nyancat_16x12.bmp")
nyan_bmp_pixel_shader.make_transparent(0)
nyan_tg = TileGrid(bitmap=nyan_bmp, pixel_shader=nyan_bmp_pixel_shader)
scaled_group.append(nyan_tg)

nyan_tg.x = 80
nyan_tg.y = 50

start_prompt = "Press A / Up" if pad.connected else "Spacebar"
score_lbl = Label(terminalio.FONT, text=start_prompt, color=0xFFFFFF, scale=2)
score_lbl.anchor_point = (0, 1)
score_lbl.anchored_position = (2, display.height - 2)
main_group.append(score_lbl)

game_over_label = Label(
    terminalio.FONT,
    text="",
    color=0xFFFFFF,
    background_color=0x000000,
    padding_top=10,
    padding_bottom=10,
    padding_left=10,
    padding_right=10,
)
game_over_label.anchor_point = (0.5, 0.5)
game_over_label.anchored_position = (display.width // 2, display.height // 2)
game_over_label.hidden = True
main_group.append(game_over_label)

display.root_group = main_group
display.auto_refresh = False

trail_coords = []
cat_speed = FALL_SPEED


def swap_trail():
    if trail_bmp[0, 0] == 1:
        trail_bmp[0, 0] = 0
        trail_bmp[0, 1] = 8
        trail_bmp[0, 2] = 7
        trail_bmp[0, 3] = 9
        trail_bmp[0, 4] = 7
        trail_bmp[0, 5] = 8
    else:
        for i in range(6):
            trail_bmp[0, i] = i + 1


def draw_trail():
    for coord in trail_coords:
        bitmaptools.blit(trail_canvas_bmp, trail_bmp, coord[0], coord[1])


def erase_trail():
    for coord in trail_coords:
        bitmaptools.fill_region(
            trail_canvas_bmp, coord[0], coord[1], coord[0] + 1, coord[1] + 6, 0
        )


def shift_trail():
    for idx in range(len(trail_coords)):
        trail_coords[idx][0] -= 1

# Changed by Gemini (Google AI)
def shift_post(post):
    global score  # pylint: disable=global-statement
    if post.x <= 0:
        score += 10
        post_pool.recycle_post(post)
        new_post = post_pool.get_post()
        new_post.x = 320 - 16
        return new_post
    post.x -= min((2 + score // 150), 5)
    return post


def exit_to_launcher():
    if pad is not None:
        pad.release()
    supervisor.set_next_code_file("/code.py", working_directory="/")
    supervisor.reload()


display.refresh(target_frames_per_second=30)
cat_y = float(nyan_tg.y) # Line added on advise of Gemini (Google AI)
playing = False
JUMP_BTNS = A_BUTTONS + B_BUTTONS + UP_BUTTONS
TRAIL_BTNS = X_BUTTONS + Y_BUTTONS

while True:
    try:
        if not playing:
            while True:
                jump_pressed = False
                if pad.connected:
                    pad.update()
                    if pad.is_any_just_pressed(START_BUTTONS) or pad.is_any_just_pressed(SELECT_BUTTONS):
                        exit_to_launcher()
                    if pad.is_any_just_pressed(JUMP_BTNS):
                        jump_pressed = True

                available = supervisor.runtime.serial_bytes_available
                if available:
                    cur_btn_val = sys.stdin.read(available)
                    if " " in cur_btn_val:
                        jump_pressed = True
                    elif "q" in cur_btn_val.lower():
                        exit_to_launcher()

                if jump_pressed:
                    cat_speed = -JUMP_SPEED
                    playing = True
                    if pad.connected:
                        pad.update()
                    break

                time.sleep(0.01)

        if first_post.check_collision(nyan_tg) or second_post.check_collision(nyan_tg):
            raise GameOverException(
                f"Kitty got distracted by the scratchers post.\nScore: {score}"
            )

        jump_pressed = False
        swap_pressed = False

        if pad.connected:
            pad.update()
            if pad.is_any_just_pressed(START_BUTTONS):
                exit_to_launcher()
            if pad.is_any_just_pressed(JUMP_BTNS):
                jump_pressed = True
            if pad.is_any_just_pressed(TRAIL_BTNS):
                swap_pressed = True

        available = supervisor.runtime.serial_bytes_available
        if available:
            cur_btn_val = sys.stdin.read(available)
            if " " in cur_btn_val:
                jump_pressed = True
            if "s" in cur_btn_val.lower():
                swap_pressed = True
            if "q" in cur_btn_val.lower():
                exit_to_launcher()

        cat_speed = min(cat_speed + FALL_SPEED, TERMINAL_VELOCITY)

        if jump_pressed:
            cat_speed = -JUMP_SPEED
            score += 1
        elif swap_pressed:
            swap_trail()
            score += 1

        cat_y += cat_speed # Line added on advise of Gemini (Google AI)
        nyan_tg.y = int(cat_y)

        if nyan_tg.y > display.height // 2 or nyan_tg.y < 0:
            raise GameOverException(f"Kitty wandered away.\nScore: {score}")

        draw_coords = [nyan_tg.x // 2, nyan_tg.y // 2]

        try:
            erase_trail()
        except ValueError as exc:
            raise GameOverException(f"Kitty wandered away.\nScore: {score}") from exc

        shift_trail()
        trail_coords.append(draw_coords)
        if len(trail_coords) > TRAIL_LENGTH:
            trail_coords.pop(0)

        draw_trail()

        first_post = shift_post(first_post)
        second_post = shift_post(second_post)

        score_lbl.text = str(score)
        display.refresh(target_frames_per_second=22) # was: =30)

    except GameOverException as e:
        prompt = (
            f"{e.msg}\nA / START: Play Again\nB / SELECT: Quit"
            if pad.connected
            else f"{e.msg}\nPress P to play again\nPress Q to quit"
        )
        game_over_label.text = prompt
        game_over_label.hidden = False
        display.refresh()
        break

# Game Over input loop
while True:
    replay = False
    quit_game = False

    if pad.connected:
        pad.update()
        if pad.is_any_just_pressed(A_BUTTONS) or pad.is_any_just_pressed(START_BUTTONS):
            replay = True
        elif pad.is_any_just_pressed(B_BUTTONS) or pad.is_any_just_pressed(SELECT_BUTTONS):
            quit_game = True

    available = supervisor.runtime.serial_bytes_available
    if available:
        cur_btn_val = sys.stdin.read(available).lower()
        if "p" in cur_btn_val:
            replay = True
        elif "q" in cur_btn_val:
            quit_game = True

    if replay:
        if pad is not None:
            pad.release()
        supervisor.set_next_code_file(
            __file__,
            working_directory=Path(__file__).parent.absolute(),
        )
        supervisor.reload()
    elif quit_game:
        exit_to_launcher()

    time.sleep(0.01)

