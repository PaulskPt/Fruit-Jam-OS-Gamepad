# SPDX-FileCopyrightText: 2025 Anne Barela for Adafruit Industries
#
# SPDX-License-Identifier: MIT
#
# Breakout - Fruit Jam version
#
# 2026-11-06 changed by Paulus Schulinck (Github @PaulskPt) with assistance of Google AI
# Added functionality to detect and use a SNES type gamecontroller
# 2026-11-09 Refactored to use shared /lib/fj_gamepad.py module
#
import sys
import time
import gc
import array
import math
import random
import atexit
import audiocore
from adafruit_fruitjam.peripherals import Peripherals
from adafruit_fruitjam.peripherals import request_display_config
import displayio
import supervisor
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle
from adafruit_display_text import label
import terminalio
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    LEFT_BUTTONS,
    RIGHT_BUTTONS,
    SELECT_BUTTONS,
    START_BUTTONS,
    HW_START,
    HW_SELECT,
)

# Send ANSI terminal escape codes to erase the console history and home the cursor
sys.stdout.write("\x1b[2J\x1b[H")
time.sleep(1)

my_debug = False
use_sound = False
use_neopixels = False
fruitjam = None
audio_output_fm_config = None
k_lbl = None

path_name = "F:/CIRCUITPY/apps/"
game_name = "Fruit_Jam_Breakout"
fn = "code.py"

# Input state
key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_space_released = True
any_key = False

displayio.release_displays()

launcher_config = LauncherConfig()

my_debug = launcher_config.data.get("my_debug", False)
if my_debug:
    print(f"my_debug from launcher_conf.json = {my_debug}")
use_sound = launcher_config.data.get("use_sound", False)
use_mouse = launcher_config.data.get("use_mouse", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)

if launcher_config.data.get("use_keyboard", False):
    if my_debug:
        print(f"{path_name}{game_name}{fn}. Initializing Keyboard Host stack...")
    use_keyboard = True
else:
    if my_debug:
        print(f"{path_name}{game_name}{fn}. Keyboard Host driver disabled. Memory optimized for application launch!")
    use_keyboard = False

if use_sound:
    audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")
    launcher_config.audio_output = audio_output_fm_config

if not my_debug:
    print(f"{path_name}{game_name}{fn}. Launcher_config checks:")
    print(f"launcher_config.use_mouse = {use_mouse}")
    print(f"launcher_config.use_gamepad = {use_gamepad}")
    print(f"launcher_config.use_keyboard = {use_keyboard}")
    print(f"launcher_config.use_sound = {use_sound}")
    print(f"launcher_config.audio_output = {launcher_config.audio_output}")

# Initialize shared GamepadManager
pad = None
if use_gamepad:
    pad = GamepadManager(check_bridge=True, debug=my_debug)
    if not pad.connected and not my_debug:
        print("Breakout: No gamepad flagged by launcher. Falling back to alternative inputs.")
        
    pad.print_controls("Breakout", (
        ("D-Pad L/R", "Move paddle"),
        ("L1 / R1", "Move paddle"),
        ("SELECT", "Start / Launch ball"),
        ("START", "Exit to main menu"),
    ))

# Initialize audio output
if use_sound:
    if not my_debug:
        print(f"audio_output_fm_config= {audio_output_fm_config}")
    fruitjam = Peripherals(audio_output=audio_output_fm_config)
    if fruitjam.dac is None:
        print("\nAre you running this on a Fruit Jam?")
        sys.exit(1)

# Initialize status LEDs
if use_neopixels:
    fruitjam.neopixels.brightness = 0.4
    fruitjam.neopixels.fill((0, 40, 0))

# Configure speaker settings
if use_sound:
    fruitjam.dac.speaker_output = True
    fruitjam.dac.dac_volume = 0
    fruitjam.dac.speaker_volume = -5
    fruitjam.dac.speaker_gain = 18


def play_tone(frequency, duration, volume=0.5):
    if not use_sound:
        return
    sample_rate = fruitjam.dac.sample_rate
    length = sample_rate // int(frequency)
    sine_wave = array.array("h", [0] * length)
    for i in range(length):
        sine_wave[i] = int((math.sin(math.pi * 2 * i / length)) * volume * (2**15 - 1))
    sine_wave_sample = audiocore.RawSample(sine_wave, sample_rate=sample_rate)
    fruitjam.audio.play(sine_wave_sample, loop=True)
    time.sleep(duration)
    fruitjam.audio.stop()


def play_paddle_hit():
    if use_sound:
        play_tone(440, 0.02)


def play_wall_hit():
    if use_sound:
        play_tone(330, 0.01)


def play_brick_hit():
    if use_sound:
        play_tone(660, 0.02)


def play_game_over():
    if use_sound:
        for i in range(5):
            play_tone(330 - i * 30, 0.1)


def play_level_win():
    if use_sound:
        sequence = [440, 440, 440, 587, 440, 587, 659]
        durations = [0.1, 0.1, 0.1, 0.3, 0.1, 0.1, 0.4]
        for freq, dur in zip(sequence, durations):
            play_tone(freq, dur)
            time.sleep(0.01)


def play_life_lost():
    if use_sound:
        play_tone(220, 0.1)
        time.sleep(0.05)
        play_tone(196, 0.2)


def play_game_start():
    if use_sound:
        play_tone(440, 0.1)
        time.sleep(0.05)
        play_tone(554, 0.1)
        time.sleep(0.05)
        play_tone(659, 0.2)


def paddle_center_pos():
    global paddle_pos_x
    paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)


gc.collect()

if my_debug:
    print("Breakout: Initializing matched 320x240 display architecture...")
request_display_config(320, 240)
display = supervisor.runtime.display

# Game constants
PADDLE_WIDTH = 40
PADDLE_HEIGHT = 5
BALL_RADIUS = 2
BRICK_ROWS = 5
BRICK_COLS = 10
BRICK_WIDTH = 30
BRICK_HEIGHT = 10
BRICK_GAP = 2
PADDLE_SPEED = 6.0
BALL_SPEED_INITIAL = 2.75
BRICK_COLORS = [0xFF4136, 0xFF851B, 0xFFDC00, 0x2ECC40, 0x0074D9]
DISPLAY_LINE = 20

# Game state
game_active = False
game_over = False
brick_count = BRICK_ROWS * BRICK_COLS
paddle_pos_x = 0.0


def check_keys() -> tuple:
    """Check for keyboard input via supervisor.runtime.serial_bytes_available."""
    l_pressed = False
    r_pressed = False
    s_pressed = False
    any_k = False

    if supervisor.runtime.serial_bytes_available:
        any_k = True
        try:
            key = sys.stdin.read(1)
            if key in ("a", "A"):
                l_pressed = True
            elif key in ("d", "D"):
                r_pressed = True
            elif key == " ":
                s_pressed = True
            elif key in ("q", "Q") or ord(key) == 27:
                sys.exit(0)
        except Exception as e:
            if not my_debug:
                print("Input error:", e)
            else:
                raise

    return (l_pressed, r_pressed, s_pressed, any_k)


def create_game_elements():
    """Create and return all game display elements."""
    global k_lbl

    game_group = displayio.Group()

    paddle = Rect(
        (display.width - PADDLE_WIDTH) // 2,
        display.height - PADDLE_HEIGHT - DISPLAY_LINE,
        PADDLE_WIDTH,
        PADDLE_HEIGHT,
        fill=0x00FFFF,
    )
    game_group.append(paddle)

    ball = Circle(
        display.width // 2,
        display.height - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3,
        BALL_RADIUS,
        fill=0xFFFFFF,
    )
    game_group.append(ball)

    bricks = []
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            brick_x = (
                col * (BRICK_WIDTH + BRICK_GAP)
                + (display.width - (BRICK_COLS * (BRICK_WIDTH + BRICK_GAP) - BRICK_GAP)) // 2
            )
            brick_y = row * (BRICK_HEIGHT + BRICK_GAP) + 30
            brick = Rect(
                brick_x,
                brick_y,
                BRICK_WIDTH,
                BRICK_HEIGHT,
                fill=BRICK_COLORS[row % len(BRICK_COLORS)],
            )
            bricks.append(brick)
            game_group.append(brick)

    score_label = label.Label(
        terminalio.FONT,
        text="Score: 0",
        color=0xFFFFFF,
        x=5,
        y=display.height - 10,
    )
    lives_label = label.Label(
        terminalio.FONT,
        text="Lives: 3",
        color=0xFFFFFF,
        x=display.width - 60,
        y=display.height - 10,
    )
    game_group.append(score_label)
    game_group.append(lives_label)

    ctrl_txt = "D-Pad: L < - > R" if use_gamepad else "A: Left   D: Right"
    controls_label = label.Label(
        terminalio.FONT,
        text=ctrl_txt,
        color=0xFFFFFF,
        x=10,
        y=display.height - 30,
    )
    game_group.append(controls_label)

    k_lbl = "SELECT" if use_gamepad else "SPACE"
    message_label = label.Label(
        terminalio.FONT,
        text="Press " + k_lbl + " to begin",
        color=0xFFFFFF,
        x=(display.width - 130) // 2,
        y=display.height // 2,
    )
    game_group.append(message_label)

    return (
        game_group,
        paddle,
        ball,
        bricks,
        score_label,
        lives_label,
        message_label,
        controls_label,
    )


(
    main_group,
    paddle,
    ball,
    bricks,
    score_label,
    lives_label,
    message_label,
    controls_label,
) = create_game_elements()
display.root_group = main_group

score = 0
lives = 3
ball_dx = 0.0
ball_dy = 0.0
ball_speed = BALL_SPEED_INITIAL
last_hit_brick = None

ball_pos_x = float(ball.x)
ball_pos_y = float(ball.y)
paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)


def ball_reset():
    global ball_dx, ball_dy, ball_pos_x, ball_pos_y
    ball_pos_x = float(display.width // 2)
    ball_pos_y = float(display.height - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3)
    ball.x = int(ball_pos_x)
    ball.y = int(ball_pos_y)
    ball_dx = 0
    ball_dy = 0


def launch_ball():
    global ball_dx, ball_dy, ball_speed
    ball_speed = BALL_SPEED_INITIAL
    angle = random.uniform(0.5, 0.8)
    ball_dx = ball_speed * random.choice([-angle, angle])
    ball_dy = -ball_speed * (1 - abs(ball_dx / ball_speed))
    controls_label.hidden = True


def update_message(text):
    message_label.text = text
    message_label.x = (display.width - len(text) * 6) // 2


ball_reset()

last_wall_hit_time = 0
sound_cooldown = 0.05

play_game_start()

lStart = True
lStop = False

start_time = time.monotonic()
last_interaction_time = start_time

def run_breakout_game():
    """Main execution container for the procedural game loop."""
    global lStart, lStop, any_key, key_left_pressed, key_right_pressed, key_space_pressed
    global key_space_released, paddle_pos_x
    global lives, score, brick_count, last_hit_brick, game_active, game_over, main_group
    global paddle, bricks, score_label, lives_label, message_label, controls_label
    global start_time, last_interaction_time, last_wall_hit_time, sound_cooldown
    global ball, ball_speed, ball_dx, ball_dy, ball_pos_x, ball_pos_y

    print(f"Waiting for {k_lbl} press to start the game")
    if use_gamepad and pad and pad.connected:
        pad.wait_for_release()
    
    while True:
        current_time = time.monotonic()

        if use_keyboard:
            key_left_pressed, key_right_pressed, key_space_pressed, any_key = check_keys()
        elif use_gamepad and pad and pad.connected:
            try:
                raw_events = pad.update()
                if raw_events:
                    last_interaction_time = current_time
                    start_time = current_time

                    # Handle Menu Click-Through Bypass
                    if lStart:
                        for btn, _ in raw_events:
                            if btn in (HW_START, HW_SELECT):
                                if my_debug:
                                    print(f"Gamepad button {btn} bypassed to prevent menu click-through.")
                                lStart = False
                                pad.flush()
                                if btn == HW_SELECT:
                                    print("Breakout game started!")
                                break

                # Query clean button states from GamepadManager
                key_left_pressed = pad.is_any_held(LEFT_BUTTONS)
                key_right_pressed = pad.is_any_held(RIGHT_BUTTONS)
                key_space_pressed = pad.is_any_held(SELECT_BUTTONS)

                if pad.is_any_just_pressed(START_BUTTONS):
                    if my_debug:
                        print("Start (= Exit game) pressed")
                    lStop = True

            except KeyboardInterrupt:
                break

        if lStop:
            print("Exiting game loop.")
            update_message("Exiting game...")
            break

        # Apply paddle movement
        if key_left_pressed and paddle_pos_x > 0:
            paddle_pos_x -= PADDLE_SPEED
            if paddle_pos_x < 0:
                paddle_pos_x = 0

        if key_right_pressed and paddle_pos_x < display.width - PADDLE_WIDTH:
            paddle_pos_x += PADDLE_SPEED
            if paddle_pos_x > display.width - PADDLE_WIDTH:
                paddle_pos_x = display.width - PADDLE_WIDTH

        paddle.x = int(paddle_pos_x)

        # Handle space/select for start/launch with debouncing
        if key_space_pressed and key_space_released:
            key_space_released = False

            if game_over:
                (
                    main_group,
                    paddle,
                    ball,
                    bricks,
                    score_label,
                    lives_label,
                    message_label,
                    controls_label,
                ) = create_game_elements()
                display.root_group = main_group
                score = 0
                lives = 3
                brick_count = BRICK_ROWS * BRICK_COLS
                game_over = False
                ball_reset()
                update_message("")
                paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)
                play_game_start()

            if not game_active and not game_over:
                game_active = True
                launch_ball()
                update_message("")
                play_tone(587, 0.1)

        if not key_space_pressed:
            key_space_released = True

        if game_active and not game_over:
            ball_pos_x += ball_dx
            ball_pos_y += ball_dy
            ball.x = int(ball_pos_x)
            ball.y = int(ball_pos_y)

            wall_hit = False
            if ball_pos_x - BALL_RADIUS <= 0:
                ball_pos_x = BALL_RADIUS + 1
                ball_dx = abs(ball_dx)
                wall_hit = True
            elif ball_pos_x + BALL_RADIUS >= display.width:
                ball_pos_x = display.width - BALL_RADIUS - 1
                ball_dx = -abs(ball_dx)
                wall_hit = True

            if ball_pos_y - BALL_RADIUS <= 0:
                ball_pos_y = BALL_RADIUS + 1
                ball_dy = abs(ball_dy)
                wall_hit = True

            if wall_hit and current_time - last_wall_hit_time > sound_cooldown:
                play_wall_hit()
                last_wall_hit_time = current_time

            if ball_pos_y + BALL_RADIUS > display.height - DISPLAY_LINE:
                lives -= 1
                lives_label.text = f"Lives: {lives}"
                play_life_lost()

                if lives <= 0:
                    game_active = False
                    game_over = True
                    if use_gamepad:
                        update_message(f"GAME OVER! Press {k_lbl} to play again, START to quit")
                    else:
                        update_message(f"GAME OVER! Press {k_lbl} to play again, Q to quit")
                    play_game_over()
                else:
                    paddle_center_pos()
                    ball_reset()
                    game_active = False
                    update_message(f"Press {k_lbl} to continue")

            paddle_collision = (
                ball_pos_y + BALL_RADIUS >= paddle.y
                and ball_pos_y - BALL_RADIUS <= paddle.y + PADDLE_HEIGHT
                and ball_pos_x + BALL_RADIUS >= paddle.x
                and ball_pos_x - BALL_RADIUS <= paddle.x + PADDLE_WIDTH
            )

            if paddle_collision:
                hit_position = (ball_pos_x - paddle.x) / PADDLE_WIDTH
                angle_factor = 2 * (hit_position - 0.5)
                ball_speed = min(ball_speed * 1.05, 4.5)
                ball_dx = ball_speed * angle_factor
                ball_dy = -ball_speed * (1 - 0.8 * abs(angle_factor))
                ball_pos_y = paddle.y - BALL_RADIUS - 1
                ball.y = int(ball_pos_y)
                play_paddle_hit()

            for brick in bricks:
                brick_collision = (
                    brick in main_group
                    and brick.x <= ball_pos_x + BALL_RADIUS
                    and brick.x + BRICK_WIDTH >= ball_pos_x - BALL_RADIUS
                    and brick.y <= ball_pos_y + BALL_RADIUS
                    and brick.y + BRICK_HEIGHT >= ball_pos_y - BALL_RADIUS
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
                        game_active = False
                        game_over = True
                        update_message(f"YOU WON! Press {k_lbl} to play again")
                        play_level_win()
                    break

            if last_hit_brick:
                still_touching = (
                    last_hit_brick.x <= ball_pos_x + BALL_RADIUS
                    and last_hit_brick.x + BRICK_WIDTH >= ball_pos_x - BALL_RADIUS
                    and last_hit_brick.y <= ball_pos_y + BALL_RADIUS
                    and last_hit_brick.y + BRICK_HEIGHT >= ball_pos_y - BALL_RADIUS
                )
                if not still_touching:
                    last_hit_brick = None

        elif not game_active and not game_over:
            ball.x = paddle.x + PADDLE_WIDTH // 2
            ball_pos_x = float(ball.x)

        display.refresh()
        time.sleep(0.026)


def atexit_callback():
    """Cleans up hardware connections and points execution back to root Launcher."""
    global main_group, bricks
    print("inside atexit callback")

    if pad is not None:
        pad.release()

    try:
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception as e:
        if my_debug:
            print(f"Failed to clear app arguments file: {e}")

    while supervisor.runtime.serial_bytes_available:
        try:
            sys.stdin.read(1)
        except Exception:
            break

    try:
        display.root_group = displayio.Group()
        main_group = None
        bricks = None
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

if __name__ == "__main__":
    gc.collect()
    if my_debug:
        print("Starting Breakout Suite App Context...")
    try:
        run_breakout_game()
    except Exception as err:
        if my_debug:
            print(f"Breakout Execution Crash isolated: {err}")
        import traceback
        traceback.print_exception(err)
        time.sleep(5)
    finally:
        if lStop:
            if my_debug:
                print("Launcher target exit flag detected. Initializing clean reload...")
            supervisor.reload()
        else:
            print("Breakout Error: Loop exited prematurely without lStop flag.")
            while True:
                time.sleep(1)
