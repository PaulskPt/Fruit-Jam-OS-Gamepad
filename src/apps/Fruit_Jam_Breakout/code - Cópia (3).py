# SPDX-FileCopyrightText: 2025 Anne Barela for Adafruit Industries
#
# SPDX-License-Identifier: MIT
#
# Breakout - Fruit Jam version
#
# 2026-11-06 changed by Paulus Schulinck (Github @PaulskPt) with assistance of Google AI
# Added functionality to detect and use a SNES type gamecontroller
#
import sys
import time
import gc
import array
import math
import random
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

# Send ANSI terminal escape codes to erase the console history and home the cursor
# \x1bc = Reset terminal, \x1b[2J = Clear screen, \x1b[H = Move cursor to top-left
sys.stdout.write("\x1b[2J\x1b[H")
time.sleep(1)

my_debug = False
use_sound = False
use_neopixels = False
fruitjam = None
audio_output_fm_config = None

key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
any_key = False  # --- ADD This line to fix the function lookup crash! ---
k_lbl = None

path_name = "F:/CIRCUITPY/apps/"
game_name = "Fruitjam_Breakout"
fn = "code.py"

# Keyboard input state
key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_space_released = True  # Track space key release to prevent multiple actions

# --- HARDWARE ALIGNMENT INJECTION ---
# Map your physical controller numbers directly to standard game action scopes
HW_LEFT   = 6  # Your D-pad left key register
HW_RIGHT  = 7 # Your D-pad right key register
HW_START  = 8  # Your START button register
HW_SELECT = 9  # Your SELECT button register
# ------------------------------------


displayio.release_displays()  # Ensure there are no active displays

launcher_config = LauncherConfig()

my_debug =  launcher_config.data.get("my_debug", False) # override the definition above
if my_debug:
    print(f"my_debug from launcher_conf.json = {my_debug}")
use_sound = launcher_config.data.get("use_sound", False)
use_mouse = launcher_config.data.get("use_mouse", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)
# Wrap your keyboard driver initialization in a safe check
if launcher_config.data.get("use_keyboard", False):
    if my_debug:
        print(f"{path_name}{game_name}{fn}. Initializing Keyboard Host stack...")
    # (Original developer keyboard setup code goes here)
    use_keyboard = launcher_config.data.get("use_keyboard", False)
else:
    if my_debug:
        print(f"{path_name}{game_name}{fn}. Keyboard Host driver disabled. Memory optimized for application launch!")
    use_keyboard = False
    
if use_sound:
    audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")   # or "headphone"
    launcher_config.audio_output = audio_output_fm_config

if not my_debug:
    print(f"{path_name}{game_name}{fn}. Launcher_config checks:")
    print(f"launcher_config.use_mouse = {use_mouse}")
    print(f"launcher_config.use_gamepad = {use_gamepad}")
    print(f"launcher_config.use_keyboard = {use_keyboard}")
    print(f"launcher_config.use_sound = {use_sound}")
    print(f"launcher_config.audio_output = {launcher_config.audio_output}")

"""
# See fruitjam.dac code lines below!
audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")   # or "headphone"
print(f"launcher_config.audio_output = {audio_output_fm_config}")

if launcher_config.audio_output_speaker or launcher_config.audio_output_headphones:
    launcher_config.audio_volume = 0.75 # max = 1.0
    print(f"audio volume set to: {str(float(launcher_config.audio_volume))}")
"""

# 3. Gamepad Engine (Heavy Asynchronous Protocol)
has_gamepad = None
gamepad = None
if use_gamepad:
    try:
        import gamepad_bridge
    except:
        print("failed to import module gamepad_bridge") # Line added by @PaulskPt
        pass
    else:
        if my_debug:
            print("import module gamepad_bridge successful")
        
        # Check the hardware register to see if a gamepad is ready to use
        has_gamepad = gamepad_bridge.verify_bridged_gamepad()
    
    if has_gamepad:
        try:
            import relic_usb_host_gamepad
        except ImportError:
            if not my_debug:
                print("failed to import module relic_usb_host_gamepad") # Line added by @PaulskPt
            gamepad = None
        else:
            if my_debug:
                print("import module relic_usb_host_gamepad successful")
            gamepad = relic_usb_host_gamepad.Gamepad()   
             
            GAMEPAD_MAP = {
                # --- Map your specific physical clone hardware indexes explicitly ---
                0: "\x1b[C",  # HW_RIGHT maps to standard right character strings
                1: "\x1b[D",  # HW_LEFT maps to standard left character strings
                8: "\n",      # HW_START maps to select string actions
                9: "\n",      # HW_SELECT maps to space bar actions
                # --------------------------------------------------------------------
                relic_usb_host_gamepad.BUTTON_UP: "\x1b[A",
                relic_usb_host_gamepad.BUTTON_JOYSTICK_UP: "\x1b[A",
                relic_usb_host_gamepad.BUTTON_DOWN: "\x1b[B",
                relic_usb_host_gamepad.BUTTON_JOYSTICK_DOWN: "\x1b[B",
                relic_usb_host_gamepad.BUTTON_LEFT: "\x1b[D",
                relic_usb_host_gamepad.BUTTON_JOYSTICK_LEFT: "\x1b[D",
                relic_usb_host_gamepad.BUTTON_RIGHT: "\x1b[C",
                relic_usb_host_gamepad.BUTTON_JOYSTICK_RIGHT: "\x1b[C",
                relic_usb_host_gamepad.BUTTON_A: "\n",
                relic_usb_host_gamepad.BUTTON_START: "\n",
                relic_usb_host_gamepad.BUTTON_SELECT: "\n", 
                relic_usb_host_gamepad.BUTTON_L1: "\x1b[5~",  
                relic_usb_host_gamepad.BUTTON_R1: "\x1b[6~",  
            }

        if gamepad is not None:
            if my_debug:
                print(f"gamepad object created. Check type: {type(gamepad)}")
            else:
                pass

    else:
        if not my_debug:
            print("Breakout: No gamepad flagged by launcher. Falling back to alternative inputs.")
        gamepad = None
    
# Initialize audio output
if use_sound:
    if not my_debug:
        print(f"audio_output_fm_config= {audio_output_fm_config}")
    fruitjam = Peripherals(audio_output=audio_output_fm_config)  # or "headphone"
    if fruitjam.dac is None:
        print("\nAre you running this on a Fruit Jam?")
        sys.exit(1)

# Initialize status LEDs
if use_neopixels:
    fruitjam.neopixels.brightness = 0.4
    fruitjam.neopixels.fill((0, 40, 0))  # Initial status: green

# Configure speaker settings
if use_sound:
    fruitjam.dac.speaker_output = True
    fruitjam.dac.dac_volume = 0         # Digital volume (-63.5 to 24.0 dB)
    fruitjam.dac.speaker_volume = -5    # Analog volume (-78.3 to 0 dB)
    fruitjam.dac.speaker_gain = 18      # Amplifier gain (6, 12, 18, or 24 dB)

# Sound effect functions
def play_tone(frequency, duration, volume=0.5):
    """Play a tone at the specified frequency for the specified duration

    Args:
        frequency (int/float): Frequency in Hz (e.g., 440 for A4)
        duration (float): Duration in seconds
        volume (float): Volume level from 0.0 to 1.0 (default 0.5)
    """
    if not use_sound:
        return
    # Get the sample rate from the DAC
    sample_rate = fruitjam.dac.sample_rate

    # Calculate length of one period of the waveform
    length = sample_rate // int(frequency)

    # Generate a sine wave for one period
    sine_wave = array.array("h", [0] * length)
    for i in range(length):
        sine_wave[i] = int((math.sin(math.pi * 2 * i / length)) * volume * (2**15 - 1))

    # Create a RawSample from the sine wave
    sine_wave_sample = audiocore.RawSample(sine_wave, sample_rate=sample_rate)

    # Play the tone
    fruitjam.audio.play(sine_wave_sample, loop=True)
    time.sleep(duration)
    fruitjam.audio.stop()

def play_paddle_hit():
    """Sound for ball hitting paddle"""
    if not use_sound:
        return
    play_tone(440, 0.02)  # was: (440, 0.05) A4, short duration

def play_wall_hit():
    """Sound for ball hitting wall"""
    if not use_sound:
        return
    play_tone(330, 0.01)  # was: (330, 0.03) E4, very short

def play_brick_hit():
    """Sound for ball hitting brick"""
    if not use_sound:
        return
    play_tone(660, 0.02)  # was: (660, 0.05) E5, short

def play_game_over():
    """Sound for game over"""
    if not use_sound:
        return
    # Descending tone
    for i in range(5):
        play_tone(330 - i*30, 0.1)

def play_level_win():
    """Sound for winning the level"""
    if not use_sound:
        return
    # Victory fanfare
    sequence = [440, 440, 440, 587, 440, 587, 659]
    durations = [0.1, 0.1, 0.1, 0.3, 0.1, 0.1, 0.4]

    for freq, dur in zip(sequence, durations):
        play_tone(freq, dur)
        time.sleep(0.01)  # Small gap between notes

def play_life_lost():
    """Sound for losing a life"""
    if not use_sound:
        return
    play_tone(220, 0.1)
    time.sleep(0.05)
    play_tone(196, 0.2)

def play_game_start():
    """Sound for game start"""
    if not use_sound:
        return
    play_tone(440, 0.1)
    time.sleep(0.05)
    play_tone(554, 0.1)
    time.sleep(0.05)
    play_tone(659, 0.2)

def paddle_center_pos():
    global paddle_pos_x
    paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)

# Clear heap space
gc.collect()

# Initialize directly at the matched 320x240 geometry floor
if my_debug:
    print("Breakout: Initializing matched 320x240 display architecture...")
request_display_config(320, 240) # (720, 400) # (320, 240)
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
PADDLE_SPEED = 6.0         # Change to make paddle speed up or slow down
BALL_SPEED_INITIAL = 2.75  # Change initial ball speed
BRICK_COLORS = [0xFF4136, 0xFF851B, 0xFFDC00, 0x2ECC40, 0x0074D9]
DISPLAY_LINE = 20  # Score is on the bottom of the display 20 px tall

# Game state
game_active = False
game_over = False
brick_count = BRICK_ROWS * BRICK_COLS

# Keyboard input state
key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_space_released = True  # Track space key release to prevent multiple actions

# --- HARDWARE ALIGNMENT INJECTION ---
# Map your physical controller numbers directly to standard game action scopes
HW_LEFT   = 6  # Your D-pad left key register
HW_RIGHT  = 7 # Your D-pad right key register
HW_START  = 8  # Your START button register
HW_SELECT = 9  # Your SELECT button register
# ------------------------------------

# Track paddle position with float for smoother movement
paddle_pos_x = 0.0

def handle_gamepad_press(key, is_pressed) -> tuple:
    global key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop
    
    if key in GAMEPAD_MAP:
        if key == HW_LEFT or key == relic_usb_host_gamepad.BUTTON_Y or key == relic_usb_host_gamepad.BUTTON_B or key == relic_usb_host_gamepad.BUTTON_L1:
            if is_pressed:
                if my_debug: print("Left pressed")
                key_left_pressed = True
            else:
                if my_debug: print("Left released")
                key_left_pressed = False
                
        elif key == HW_RIGHT or key == relic_usb_host_gamepad.BUTTON_X or key == relic_usb_host_gamepad.BUTTON_A or key == relic_usb_host_gamepad.BUTTON_R1:
            if is_pressed:
                if my_debug: print("Right pressed")
                key_right_pressed = True
            else:
                if my_debug: print("Right released")
                key_right_pressed = False
                
        elif key == HW_SELECT:
            if is_pressed:
                if my_debug: print("Select (= Space) pressed")
                key_space_pressed = True
            else:
                key_space_pressed = False
                
        elif key == HW_START and is_pressed:
            if my_debug: print("Start (= Exit game) pressed")
            lStop = True  # We're out of here
    else:
        if not my_debug:
            print(f"unhandled key: \"{key}\"")
        else:
            pass

    return (key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop)


def check_keys() -> tuple:
    """
    Check for keyboard input via supervisor.runtime.serial_bytes_available
    Returns tuple of (key_left_pressed, key_right_pressed, key_space_pressed, any_key)
    """
    l_pressed = False
    r_pressed = False
    s_pressed = False
    any_key = False

    # Check if serial data is available
    if supervisor.runtime.serial_bytes_available:
        any_key = True
        try:
            key = sys.stdin.read(1)
            if key in ('a', 'A'):    # Left movement
                l_pressed = True
            elif key in ('d', 'D'):  # Right movement
                r_pressed = True
            elif key == ' ':         # Space for start/launch
                s_pressed = True
            elif key in ('q', 'Q') or ord(key) == 27:  # q, Q, or ESC is quit
                sys.exit(0)  # We're out of here
        except Exception as e:       # pylint: disable=broad-except
            if not my_debug:
                print("Input error:", e)
            else:
                raise

    return (l_pressed, r_pressed, s_pressed, any_key)

# pylint: disable=redefined-outer-name
def create_game_elements():
    """Create and return all game display elements"""
    global k_lbl
    
    game_group = displayio.Group()

    # Paddle
    paddle = Rect(
        (display.width - PADDLE_WIDTH) // 2,
        display.height - PADDLE_HEIGHT - DISPLAY_LINE,
        PADDLE_WIDTH,
        PADDLE_HEIGHT,
        fill=0x00FFFF
    )
    game_group.append(paddle)

    # Ball
    ball = Circle(
        display.width // 2,
        display.height - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3,
        BALL_RADIUS,
        fill=0xFFFFFF
    )
    game_group.append(ball)

    # Bricks
    bricks = []
    for row in range(BRICK_ROWS):
        for col in range(BRICK_COLS):
            # Calculate brick position with appropriate spacing
            brick_x = col * (BRICK_WIDTH + BRICK_GAP) + \
                     (display.width - (BRICK_COLS * (BRICK_WIDTH + BRICK_GAP)
                      - BRICK_GAP)) // 2
            brick_y = row * (BRICK_HEIGHT + BRICK_GAP) + 30  # Start a bit down from top

            brick = Rect(
                brick_x,
                brick_y,
                BRICK_WIDTH,
                BRICK_HEIGHT,
                fill=BRICK_COLORS[row % len(BRICK_COLORS)]
            )
            bricks.append(brick)
            game_group.append(brick)

    # Score and lives
    score_label = label.Label(
        terminalio.FONT,
        text="Score: 0",
        color=0xFFFFFF,
        x=5,
        y=display.height - 10
    )
    lives_label = label.Label(
        terminalio.FONT,
        text="Lives: 3",
        color=0xFFFFFF,
        x=display.width - 60,
        y=display.height - 10
    )
    game_group.append(score_label)
    game_group.append(lives_label)

    # Controls info
    if use_gamepad:
        ctrl_txt="D-Pad: L < - > R"
    else:
        ctrl_txt="A: Left   D: Right"
    
    controls_label = label.Label(
        terminalio.FONT,
        text=ctrl_txt,
        color=0xFFFFFF,
        x=10,
        y=display.height - 30
    )
    game_group.append(controls_label)

    if use_gamepad:
        k_lbl = "SELECT"
    else:
        k_lbl = "SPACE"
    
    # Start/game over message
    message_label = label.Label(
        terminalio.FONT,
        text="Press " + k_lbl + " to begin",
        color=0xFFFFFF,
        x=(display.width - 130) // 2,
        y=display.height // 2
    )
    game_group.append(message_label)

    return (game_group, paddle, ball, bricks, score_label,
            lives_label, message_label, controls_label)

# Create initial game elements
main_group, paddle, ball, bricks, score_label, lives_label, message_label, \
    controls_label = create_game_elements()
display.root_group = main_group

# Set display
# request_display_config(320, 240) # (720, 400) # (320, 240)

# Game variables
score = 0
lives = 3
ball_dx = 0.0
ball_dy = 0.0
ball_speed = BALL_SPEED_INITIAL
last_hit_brick = None

# Track actual ball position with floats
ball_pos_x = float(ball.x)
ball_pos_y = float(ball.y)

# Initialize paddle position tracking
paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)

def ball_reset():
    """Reset the ball position and set it initially stationary"""
    global ball_dx, ball_dy, ball_pos_x, ball_pos_y  # pylint: disable=global-statement
    ball_pos_x = float(display.width // 2)
    ball_pos_y = float(display.height - PADDLE_HEIGHT - DISPLAY_LINE - BALL_RADIUS * 3)
    ball.x = int(ball_pos_x)
    ball.y = int(ball_pos_y)
    ball_dx = 0
    ball_dy = 0

def launch_ball():
    """Launch the ball in a random upward direction"""
    global ball_dx, ball_dy, ball_speed  # pylint: disable=global-statement
    ball_speed = BALL_SPEED_INITIAL
    angle = random.uniform(0.5, 0.8)  # Launch at angle between 45-65 degrees
    ball_dx = ball_speed * random.choice([-angle, angle])
    # Ensure consistent speed
    ball_dy = -ball_speed * (1 - abs(ball_dx/ball_speed))
    controls_label.hidden = True

def update_message(text):
    """Update the message text"""
    message_label.text = text
    # Center text (approximate width)
    message_label.x = (display.width - len(text) * 6) // 2

# Game loop
ball_reset()

# Track last collision for sound effect throttling
last_wall_hit_time = 0
sound_cooldown = 0.05  # Minimum time between similar sound effects

# Play startup sound
play_game_start()

lStart = True  # Flag to ignore initial Start button press from main menu
lStop = False

start_time = time.monotonic()  # Track start time for potential future use (e.g., timing events)
interval_time = 0.1 # Time interval for checking inputs and updating game state (can be adjusted for performance)
elapsed_time = 0
last_interaction_time = start_time

# ==============================================================================
# --- APPLICATION RUN ENGINE & HARDWARE RESET ARCHITECTURE ---
# ==============================================================================

def run_breakout_game():
    """Main execution container for the procedural game loop."""
    # --- FIXED: Explicitly declare any_key and lStop as global variables here ---
    global lStart, lStop, any_key, key_left_pressed, key_right_pressed, key_space_pressed
    global HW_START, HW_SELECT
    # ---------------------------------------------------------------------------
    global key_space_released, paddle_pos_x
    global lives, score, brick_count, last_hit_brick, game_active, game_over, main_group
    global paddle, bricks, score_label, lives_label, message_label, controls_label
    global start_time, last_interaction_time, last_wall_hit_time, sound_cooldown
    global ball, ball_speed, ball_dx, ball_dy, ball_pos_x, ball_pos_y

    print(f"Waiting for {k_lbl} press to start the game")

    while True:
        current_time = time.monotonic()
        
        if use_keyboard:
            key_left_pressed, key_right_pressed, key_space_pressed, any_key = check_keys()
        elif use_gamepad:
            try:
                if gamepad and gamepad.update():
                    for event in gamepad.events:
                        # --- ADD THIS RAW CODES MONITOR LINE ---
                        if my_debug:
                            print(f"RAW CONTROLLER PACKET -> Key Number: {event.key_number} | Pressed State: {event.pressed}")
                        # --------------------------------------
                        
                        # 1. Handle Menu Click-Through Bypass Layout
                        if lStart:
                            if event.key_number == HW_START or event.key_number == HW_SELECT: # Check both Select/Start clone pins
                                if my_debug:
                                    print(f"Gamepad button {event.key_number} bypassed to prevent menu click-through.")
                                lStart = False
                                # Safely exhaust all elements in the tuple buffer to drain it completely
                                for _ in gamepad.events: pass
                            if event.key_number == HW_START:
                                continue
                            elif event.key_number == HW_SELECT:
                                print("Breakout game started!")

                        # 2. Complete State Management delegated to your function
                        # This single line handles both press (True) and release (False) beautifully!
                        key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop = handle_gamepad_press(event.key_number, event.pressed)
                        
                        last_interaction_time = time.monotonic()
                        start_time = time.monotonic()
            except KeyboardInterrupt:
                break

        if lStop:
            print("Exiting game loop.")
            update_message("Exiting game...")
            break
        
        # Apply paddle movement ONLY if keys are currently pressed
        if key_left_pressed and paddle_pos_x > 0:
            paddle_pos_x -= PADDLE_SPEED
            if paddle_pos_x < 0:
                paddle_pos_x = 0

        if key_right_pressed and paddle_pos_x < display.width - PADDLE_WIDTH:
            paddle_pos_x += PADDLE_SPEED
            if paddle_pos_x > display.width - PADDLE_WIDTH:
                paddle_pos_x = display.width - PADDLE_WIDTH

        paddle.x = int(paddle_pos_x)

        # Handle space bar for start/launch with debouncing
        if key_space_pressed and key_space_released:
            key_space_released = False

            if game_over:
                (main_group, paddle, ball, bricks, score_label,
                 lives_label, message_label, controls_label) = create_game_elements()
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
                ball_pos_y + BALL_RADIUS >= paddle.y and
                ball_pos_y - BALL_RADIUS <= paddle.y + PADDLE_HEIGHT and
                ball_pos_x + BALL_RADIUS >= paddle.x and
                ball_pos_x - BALL_RADIUS <= paddle.x + PADDLE_WIDTH
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
                        game_active = False
                        game_over = True
                        update_message(f"YOU WON! Press {k_lbl} to play again")
                        play_level_win()
                    break

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

        display.refresh()
        # --- ADJUST THIS LINE AT THE BOTTOM OF THE LOOP ---
        # A 20ms sleep caps the frame processing at ~50fps, dropping 
        # the USB host polling pressure dramatically and lowering audio hum.
        time.sleep(0.026) # was: 0.016

# --- REGISTER RECOVERY TEARDOWN ---
import atexit

def atexit_callback():
    """
    Cleans up hardware connections, wipes application argument traces, 
    and redirects execution pointer cleanly back to the root Launcher.
    """
    request_display_config(720, 400) # (720, 400) # (320, 240)
    
    print("inside atexit callback")

    # 1. Clean up local input footprints safely
    if 'gamepad' in locals() and gamepad is not None:
        try:
            if hasattr(gamepad, "release"):
                gamepad.release()
        except Exception as e:
            print(f"Error releasing gamepad hardware: {e}")

    # #2. Clear out this app's specific argument footprints to prevent boot loops
    try:
        if my_debug:
            print("Clearing Breakout argument footprint cache...")
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception as e:
        if my_debug:
            print(f"Failed to clear app arguments file: {e}")
        else:
            raise

    # #3. Clear lingering serial input buffer remnants
    if my_debug:
        print("Flushing input buffers...")
    while supervisor.runtime.serial_bytes_available:
        try:
            sys.stdin.read(1)
        except Exception:
            break

    # #4. Clear the active display group to allow smooth launcher canvas generation
    if my_debug:
        print("Blanking display canvas groups...")
    try:
        display.root_group = displayio.Group()
        display.refresh()
    except Exception as e:
        if my_debug:
            print(f"Bypassed graphics group clearing: {e}")
        else:
            pass

    # #5. Redirect the supervisor execution pointer back to the main menu root
    if my_debug:
        print("Pointing boot configuration back to root launcher...")
    supervisor.set_next_code_file(
        "/code.py",
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/"
    )

    # #6. Trigger a physical hardware reset to clean the heap for the launcher
    import microcontroller
    if my_debug:
        print("Executing complete hardware reset for a fresh menu canvas floor...")
    microcontroller.reset()

# --- ATTACH THE EVENT HANDLER REGISTRATION ---
atexit.register(atexit_callback)

# --- ENTRY POINT EXECUTOR ---
if __name__ == "__main__":
    gc.collect()
    if my_debug:
        print("Starting Breakout Suite App Context...")
    try:
        # Run the primary game execution loop container
        run_breakout_game()
    except Exception as err:
        # Catch and print the exact error message so it doesn't fail silently
        if my_debug:
            print(f"Breakout Execution Crash isolated: {err}")
        import traceback
        traceback.print_exception(err)
        time.sleep(5) # Keep REPL alive to read the traceback text
    finally:
        # ONLY reload if the game loop was explicitly requested to terminate via lStop
        if lStop:
            if my_debug:
                print("Launcher target exit flag detected. Initializing clean reload...")
            supervisor.reload()
        else:
            print("Breakout Error: Loop exited prematurely without lStop flag.")
            # Keep script alive in a fallback loop so you can access REPL
            while True:
                time.sleep(1)
