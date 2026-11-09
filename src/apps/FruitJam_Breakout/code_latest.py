# SPDX-FileCopyrightText: 2025 Anne Barela for Adafruit Industries
#
# SPDX-License-Identifier: MIT
#
# Breakout - Fruit Jam version
# Modified by @PaulskPt to add gamepad support and sound effects
# Optimized for RP2350B HSTX Stability

import sys
import time
import array
import math
import random
import audiocore
import displayio
import supervisor
import gc
import synthio
from adafruit_fruitjam.peripherals import Peripherals
from adafruit_fruitjam.peripherals import request_display_config
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle
from adafruit_display_text import label
import terminalio

use_keyboard = False
gamepad = None
lStop = False

# Keyboard or gamepad input state
key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_space_released = True
any_key = False

try:
    relic_usb_host_gamepad = __import__("relic_usb_host_gamepad")
except ImportError:
    raise RuntimeError("relic_usb_host_gamepad library not found.\nPlease install it to use the gamepad functionality.")
else:
    gamepad = relic_usb_host_gamepad.Gamepad()

    GAMEPAD_MAP = {
        relic_usb_host_gamepad.BUTTON_A:      ["\x1b[A",  "Button A",              "Up"],
        relic_usb_host_gamepad.BUTTON_B:      ["\x1b[B",  "Button B",              "Down"],
        relic_usb_host_gamepad.BUTTON_X:      ["\x1b[X",  "Button X",              "Left"],
        relic_usb_host_gamepad.BUTTON_Y:      ["\x1b[Y",  "Button Y",              "Right"],
        relic_usb_host_gamepad.BUTTON_UP:     ["\x1b[a",  "D-Pad Up",              "Up"],
        relic_usb_host_gamepad.BUTTON_DOWN:   ["\x1b[b",  "D-Pad Down",            "Down"],
        relic_usb_host_gamepad.BUTTON_LEFT:   ["\x1b[d",  "D-Pad Left",            "Left"],
        relic_usb_host_gamepad.BUTTON_RIGHT:  ["\x1b[c",  "D-Pad Right",           "Right"],
        relic_usb_host_gamepad.BUTTON_START:  ["\n",      "Button Start",          "Start"],
        relic_usb_host_gamepad.BUTTON_SELECT: ["\x1b[E",  "Button Select",         "Select"],
        relic_usb_host_gamepad.BUTTON_L1:     ["\x1b[5~", "Button Left Shoulder",  "Left Shoulder"],
        relic_usb_host_gamepad.BUTTON_R1:     ["\x1b[6~", "Button Right Shoulder", "Right Shoulder"]
    }

# Safely tear down launcher memory and force GC to clear a large chunk for 320x240
displayio.release_displays()
gc.collect()

# Initialize speaker
fruit_jam = Peripherals(audio_output="speaker")
if fruit_jam.dac is None:
    sys.exit(1)

# Initialize status LEDs
fruit_jam.neopixels.brightness = 0.4
fruit_jam.neopixels.fill((0, 40, 0))

# Configure speaker settings
fruit_jam.dac.speaker_output = True
fruit_jam.dac.dac_volume = 0
fruit_jam.dac.speaker_volume = 0
fruit_jam.dac.speaker_gain = 24

# --- Hardware Synthesizer Setup ---
# Attach the synth engine directly to the Fruit Jam's audio output channel
synth = synthio.Synthesizer(sample_rate=fruit_jam.dac.sample_rate)
fruit_jam.audio.play(synth)

# Create a reusable Note object
current_note = synthio.Note(frequency=440)
# Non-Blocking Audio Control
tone_stop_time = 0.0

def play_tone(frequency, duration):
    """Instantly play a precise note using native hardware synthesis"""
    global tone_stop_time
    current_note.frequency = int(frequency)
    
    # Press the note on the synthesizer channel
    synth.press(current_note)
    tone_stop_time = time.monotonic() + duration

def check_audio_timer():
    """Monitors note durations and releases them naturally"""
    global tone_stop_time
    if tone_stop_time > 0.0 and time.monotonic() >= tone_stop_time:
        # Release the note smoothly
        synth.release(current_note)
        tone_stop_time = 0.0

# Map the game triggers to pure synth frequencies
def play_paddle_hit(): play_tone(440, 0.05)   # A4 Note
def play_wall_hit():   play_tone(330, 0.03)   # E4 Note
def play_brick_hit():  play_tone(660, 0.05)   # E5 Note
def play_game_over():  play_tone(220, 0.3)    # Low tone
def play_level_win():  play_tone(587, 0.4)    # High fanfare tone
def play_life_lost():  play_tone(196, 0.25)   # Low drop note
def play_game_start(): play_tone(554, 0.15)   # Bright starting note

# Initialize display at hardware-stable 320x240 resolution
request_display_config(320, 240)
display = supervisor.runtime.display
display.auto_refresh = True

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240

# Game constants
PADDLE_WIDTH = 40
PADDLE_HEIGHT = 5
BALL_RADIUS = 2
BRICK_ROWS = 5
BRICK_COLS = 10
BRICK_WIDTH = 28
BRICK_HEIGHT = 8
BRICK_GAP = 2
PADDLE_SPEED = 5.0
BALL_SPEED_INITIAL = 2.5
BRICK_COLORS = [0xFF4136, 0xFF851B, 0xFFDC00, 0x2ECC40, 0x0074D9]
DISPLAY_LINE = 20

game_active = False
game_over = False
brick_count = BRICK_ROWS * BRICK_COLS
paddle_pos_x = float((SCREEN_WIDTH - PADDLE_WIDTH) // 2)
game_boot_time = 0.0

def handle_gamepad_press(key):
    global key_left_pressed, key_right_pressed, key_space_pressed, lStop
    if key in GAMEPAD_MAP:
        if key == relic_usb_host_gamepad.BUTTON_LEFT or key == relic_usb_host_gamepad.BUTTON_X:
            key_left_pressed = True
        elif key == relic_usb_host_gamepad.BUTTON_RIGHT or key == relic_usb_host_gamepad.BUTTON_Y:
            key_right_pressed = True
        elif key in (relic_usb_host_gamepad.BUTTON_SELECT, relic_usb_host_gamepad.BUTTON_A, relic_usb_host_gamepad.BUTTON_B):
            key_space_pressed = True
        elif key == relic_usb_host_gamepad.BUTTON_START:
            lStop = True

def check_keys():
    global key_left_pressed, key_right_pressed, key_space_pressed, any_key
    key_left_pressed = False
    key_right_pressed = False
    key_space_pressed = False
    any_key = False

    if supervisor.runtime.serial_bytes_available:
        any_key = True
        try:
            key = sys.stdin.read(1)
            if key in ('a', 'A'):
                key_left_pressed = True
            elif key in ('d', 'D'):
                key_right_pressed = True
            elif key == ' ':
                key_space_pressed = True
            elif key in ('q', 'Q') or ord(key) == 27:
                sys.exit(0)
        except Exception:
            pass

def create_game_elements():
    game_group = displayio.Group()

    paddle = Rect((SCREEN_WIDTH - PADDLE_WIDTH) // 2, SCREEN_HEIGHT - PADDLE_HEIGHT - DISPLAY_LINE, PADDLE_WIDTH, PADDLE_HEIGHT, fill=0x00FFFF)
    game_group.append(paddle)

    ball = Circle(SCREEN_WIDTH // 2, SCREEN_HEIGHT - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3, BALL_RADIUS, fill=0xFFFFFF)
    game_group.append(ball)

    bricks = []
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            brick_x = col * (BRICK_WIDTH + BRICK_GAP) + ((SCREEN_WIDTH - (BRICK_COLS * (BRICK_WIDTH + BRICK_GAP) - BRICK_GAP)) // 2)
            brick_y = row * (BRICK_HEIGHT + BRICK_GAP) + 30
            brick = Rect(brick_x, brick_y, BRICK_WIDTH, BRICK_HEIGHT, fill=BRICK_COLORS[row % len(BRICK_COLORS)])
            bricks.append(brick)
            game_group.append(brick)

    score_label = label.Label(terminalio.FONT, text="Score: 0", color=0xFFFFFF, x=5, y=SCREEN_HEIGHT - 10)
    lives_label = label.Label(terminalio.FONT, text="Lives: 3", color=0xFFFFFF, x=SCREEN_WIDTH - 60, y=SCREEN_HEIGHT - 10)
    game_group.append(score_label)
    game_group.append(lives_label)

    controls_label = label.Label(terminalio.FONT, text="D-Pad: Move", color=0xFFFFFF, x=10, y=SCREEN_HEIGHT - 30)
    game_group.append(controls_label)

    message_label = label.Label(terminalio.FONT, text="Press SELECT to begin", color=0xFFFFFF, x=(SCREEN_WIDTH - 130) // 2, y=SCREEN_HEIGHT // 2)
    game_group.append(message_label)

    return (game_group, paddle, ball, bricks, score_label, lives_label, message_label, controls_label)

main_group, paddle, ball, bricks, score_label, lives_label, message_label, controls_label = create_game_elements()
display.root_group = main_group

score = 0
lives = 3
ball_dx, ball_dy = 0.0, 0.0
ball_speed = BALL_SPEED_INITIAL
last_hit_brick = None

ball_pos_x = float(ball.x)
ball_pos_y = float(ball.y)
paddle_pos_x = float((SCREEN_WIDTH - PADDLE_WIDTH) // 2)

def reset_ball():
    global ball_dx, ball_dy, ball_pos_x, ball_pos_y
    ball_pos_x = float(SCREEN_WIDTH // 2)
    ball_pos_y = float(SCREEN_HEIGHT - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3)
    ball.x = int(ball_pos_x)
    ball.y = int(ball_pos_y)
    ball_dx, ball_dy = 0, 0

def launch_ball():
    global ball_dx, ball_dy, ball_speed
    ball_speed = BALL_SPEED_INITIAL
    angle = random.uniform(0.5, 0.7)
    ball_dx = ball_speed * random.choice([-angle, angle])
    ball_dy = -ball_speed * (1 - abs(ball_dx/ball_speed))
    controls_label.hidden = True

def update_message(text):
    message_label.text = text
    message_label.x = (SCREEN_WIDTH - len(text) * 6) // 2

reset_ball()
last_wall_hit_time = 0
sound_cooldown = 0.05

play_game_start()

# Force initial display draw before running loop
display.refresh()

game_boot_time = time.monotonic()

while True:
    current_time = time.monotonic()
    check_audio_timer()

    if use_keyboard:
        check_keys()
    else:
        try:
            if gamepad and gamepad.update():
                for event in gamepad.events:
                    if event.pressed and (current_time - game_boot_time < 0.5):
                        continue

                    if event.pressed:
                        handle_gamepad_press(event.key_number)
                    elif event.released:
                        if event.key_number in (relic_usb_host_gamepad.BUTTON_LEFT, relic_usb_host_gamepad.BUTTON_X):
                            key_left_pressed = False
                        elif event.key_number in (relic_usb_host_gamepad.BUTTON_RIGHT, relic_usb_host_gamepad.BUTTON_Y):
                            key_right_pressed = False
                        elif event.key_number in (relic_usb_host_gamepad.BUTTON_SELECT, relic_usb_host_gamepad.BUTTON_A, relic_usb_host_gamepad.BUTTON_B):
                            key_space_pressed = False
                            key_space_released = True
        except KeyboardInterrupt:
            break

    if lStop:
        break

    # --- Paddle Movement Calculation ---
    if key_left_pressed and paddle_pos_x > 0:
        paddle_pos_x -= PADDLE_SPEED
        if paddle_pos_x < 0:
            paddle_pos_x = 0

    if key_right_pressed and paddle_pos_x < SCREEN_WIDTH - PADDLE_WIDTH:
        paddle_pos_x += PADDLE_SPEED
        if paddle_pos_x > SCREEN_WIDTH - PADDLE_WIDTH:
            paddle_pos_x = SCREEN_WIDTH - PADDLE_WIDTH

    paddle.x = int(paddle_pos_x)

    # --- Start Button / Debouncing Matrix ---
    if key_space_pressed and key_space_released:
        key_space_released = False

        if game_over:
            main_group, paddle, ball, bricks, score_label, lives_label, message_label, controls_label = create_game_elements()
            display.root_group = main_group
            score, lives = 0, 3
            brick_count = BRICK_ROWS * BRICK_COLS
            game_over = False
            reset_ball()
            update_message("")
            paddle_pos_x = float((SCREEN_WIDTH - PADDLE_WIDTH) // 2)
            play_game_start()

        if not game_active and not game_over:
            game_active = True
            launch_ball()
            update_message("")

    if not key_space_pressed:
        key_space_released = True

    # --- Core Active Gameplay and Physics ---
    if game_active and not game_over:
        ball_pos_x += ball_dx
        ball_pos_y += ball_dy
        ball.x = int(ball_pos_x)
        ball.y = int(ball_pos_y)

        # Wall Collisions
        wall_hit = False
        if ball_pos_x - BALL_RADIUS <= 0:
            ball_pos_x = BALL_RADIUS + 1
            ball_dx = abs(ball_dx)
            wall_hit = True
        elif ball_pos_x + BALL_RADIUS >= SCREEN_WIDTH:
            ball_pos_x = SCREEN_WIDTH - BALL_RADIUS - 1
            ball_dx = -abs(ball_dx)
            wall_hit = True

        if ball_pos_y - BALL_RADIUS <= 0:
            ball_pos_y = BALL_RADIUS + 1
            ball_dy = abs(ball_dy)
            wall_hit = True

        if wall_hit and current_time - last_wall_hit_time > sound_cooldown:
            play_wall_hit()
            last_wall_hit_time = current_time

        # Death Conditions
        if ball_pos_y + BALL_RADIUS > SCREEN_HEIGHT - DISPLAY_LINE:
            lives -= 1
            lives_label.text = f"Lives: {lives}"
            play_life_lost()

            if lives <= 0:
                game_active, game_over = False, True
                update_message("GAME OVER - Press SELECT to play again")
                play_game_over()
            else:
                reset_ball()
                game_active = False
                update_message("Press SELECT to continue")

        # Paddle Collision Handling
        paddle_collision = (
            ball_pos_y + BALL_RADIUS >= paddle.y and
            ball_pos_y - BALL_RADIUS <= paddle.y + PADDLE_HEIGHT and
            ball_pos_x + BALL_RADIUS >= paddle.x and
            ball_pos_x - BALL_RADIUS <= paddle.x + PADDLE_WIDTH
        )

        if paddle_collision:
            hit_position = (ball_pos_x - paddle.x) / PADDLE_WIDTH
            angle_factor = 2 * (hit_position - 0.5)
            ball_speed = min(ball_speed * 1.03, 4.0)
            ball_dx = ball_speed * angle_factor
            ball_dy = -ball_speed * (1 - 0.8 * abs(angle_factor))
            ball_pos_y = paddle.y - BALL_RADIUS - 1
            ball.y = int(ball_pos_y)
            play_paddle_hit()

        # Brick Collision Engine Loop
        for brick in bricks:
            brick_collision = (
                brick in main_group and
                brick.x <= ball_pos_x + BALL_RADIUS and
                brick.x + BRICK_WIDTH >= ball_pos_x - BALL_RADIUS and
                brick.y <= ball_pos_y + BALL_RADIUS and
                brick.y + BRICK_HEIGHT >= ball_pos_y - BALL_RADIUS
            )

            if brick_collision:
                if brick == last_hit_brick:
                    continue
                last_hit_brick = brick
                main_group.remove(brick)
                brick_count -= 1

                dx1 = ball_pos_x - brick.x
                dx2 = brick.x + BRICK_WIDTH - ball_pos_x
                dy1 = ball_pos_y - brick.y
                dy2 = brick.y + BRICK_HEIGHT - ball_pos_y
                min_dist = min(dx1, dx2, dy1, dy2)

                if min_dist in (dy1, dy2):
                    ball_dy = -ball_dy
                else:
                    ball_dx = -ball_dx

                score += 10
                score_label.text = f"Score: {score}"
                play_brick_hit()

                if brick_count <= 0:
                    game_active, game_over = False, True
                    update_message("YOU WIN! Press SELECT to play again")
                    play_level_win()
                break

        # Safety Cooldown Check
        if last_hit_brick:
            still_touching = (
                last_hit_brick.x <= ball_pos_x + BALL_RADIUS and
                last_hit_brick.x + BRICK_WIDTH >= ball_pos_x - BALL_RADIUS and
                last_hit_brick.y <= ball_pos_y + BALL_RADIUS and
                last_hit_brick.y + BRICK_HEIGHT >= ball_pos_y - BALL_RADIUS
            )
            if not still_touching:
                last_hit_brick = None

    elif not game_active and not game_over:
        ball.x = paddle.x + PADDLE_WIDTH // 2
        ball_pos_x = float(ball.x)

    time.sleep(0.016)
