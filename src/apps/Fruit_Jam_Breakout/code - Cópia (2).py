# SPDX-FileCopyrightText: 2025 Anne Barela for Adafruit Industries
#
# SPDX-License-Identifier: MIT
#
# Breakout - Fruit Jam version

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

my_debug = True
key_left_pressed = None
key_right_pressed = None
key_space_pressed = None
any_key = None
k_lbl = None

displayio.release_displays()  # Ensure there are no active displays

launcher_config = LauncherConfig()

use_mouse = getattr(launcher_config, "use_mouse", False)
use_gamepad = getattr(launcher_config, "use_gamepad", True)
# Wrap your keyboard driver initialization in a safe check
if getattr(launcher_config, "use_keyboard", False):
    print("/code.py: Initializing Keyboard Host stack...")
    # (Original developer keyboard setup code goes here)
    use_keyboard = getattr(launcher_config, "use_keyboard", False)
else:
    print("/code.py: Keyboard Host driver disabled. Memory optimized for application launch!")
    use_keyboard = False
audio_output_fm_config = getattr(launcher_config, "audio_output", "speaker")   # or "headphone"

print("f:/CIRCUITPY/Fruitjam_Breakout/code.py: launcher_config checks:")
print(f"launcher_config.use_mouse = {use_mouse}")
print(f"launcher_config.use_gamepad = {use_gamepad}")
print(f"launcher_config.use_keyboard = {use_keyboard}")

"""
# See fruit_jam.dac code lines below!
audio_output_fm_config = getattr(launcher_config, "audio_output", "speaker")   # or "headphone"
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
        print("import module gamepad_bridge successful")
        
        # Check the hardware register to see if a gamepad is ready to use
        has_gamepad = gamepad_bridge.verify_bridged_gamepad()
    
    if has_gamepad:
        try:
            import relic_usb_host_gamepad
        except ImportError:
            print("failed to import module relic_usb_host_gamepad") # Line added by @PaulskPt
            gamepad = None
        else:
            print("import module relic_usb_host_gamepad successful")
            gamepad = relic_usb_host_gamepad.Gamepad()
            GAMEPAD_MAP = {
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
                relic_usb_host_gamepad.BUTTON_SELECT: "\n", # ["\x1b[E",  "Button Select",         "Select"],    #  9 = Select
                relic_usb_host_gamepad.BUTTON_L1: "\x1b[5~",  # PGUP
                relic_usb_host_gamepad.BUTTON_R1: "\x1b[6~",  # PGDN
            }
            
        if gamepad is not None:
            print(f"gamepad object created. Check type: {type(gamepad)}")

    else:
        print("Breakout: No gamepad flagged by launcher. Falling back to alternative inputs.")
        gamepad = None
    
# Initialize audio output
fruit_jam = Peripherals(audio_output=audio_output_fm_config)  # or "headphone"
if fruit_jam.dac is None:
    print("\nAre you running this on a Fruit Jam?")
    sys.exit(1)

# Initialize status LEDs
fruit_jam.neopixels.brightness = 0.4
fruit_jam.neopixels.fill((0, 40, 0))  # Initial status: green

# Configure speaker settings
fruit_jam.dac.speaker_output = True
fruit_jam.dac.dac_volume = 0         # Digital volume (-63.5 to 24.0 dB)
fruit_jam.dac.speaker_volume = -5    # Analog volume (-78.3 to 0 dB)
fruit_jam.dac.speaker_gain = 18      # Amplifier gain (6, 12, 18, or 24 dB)

# Sound effect functions
def play_tone(frequency, duration, volume=0.5):
    """Play a tone at the specified frequency for the specified duration

    Args:
        frequency (int/float): Frequency in Hz (e.g., 440 for A4)
        duration (float): Duration in seconds
        volume (float): Volume level from 0.0 to 1.0 (default 0.5)
    """
    # Get the sample rate from the DAC
    sample_rate = fruit_jam.dac.sample_rate

    # Calculate length of one period of the waveform
    length = sample_rate // int(frequency)

    # Generate a sine wave for one period
    sine_wave = array.array("h", [0] * length)
    for i in range(length):
        sine_wave[i] = int((math.sin(math.pi * 2 * i / length)) * volume * (2**15 - 1))

    # Create a RawSample from the sine wave
    sine_wave_sample = audiocore.RawSample(sine_wave, sample_rate=sample_rate)

    # Play the tone
    fruit_jam.audio.play(sine_wave_sample, loop=True)
    time.sleep(duration)
    fruit_jam.audio.stop()

def play_paddle_hit():
    """Sound for ball hitting paddle"""
    play_tone(440, 0.05)  # A4, short duration

def play_wall_hit():
    """Sound for ball hitting wall"""
    play_tone(330, 0.03)  # E4, very short

def play_brick_hit():
    """Sound for ball hitting brick"""
    play_tone(660, 0.05)  # E5, short

def play_game_over():
    """Sound for game over"""
    # Descending tone
    for i in range(5):
        play_tone(330 - i*30, 0.1)

def play_level_win():
    """Sound for winning the level"""
    # Victory fanfare
    sequence = [440, 440, 440, 587, 440, 587, 659]
    durations = [0.1, 0.1, 0.1, 0.3, 0.1, 0.1, 0.4]

    for freq, dur in zip(sequence, durations):
        play_tone(freq, dur)
        time.sleep(0.01)  # Small gap between notes

def play_life_lost():
    """Sound for losing a life"""
    play_tone(220, 0.1)
    time.sleep(0.05)
    play_tone(196, 0.2)

def play_game_start():
    """Sound for game start"""
    play_tone(440, 0.1)
    time.sleep(0.05)
    play_tone(554, 0.1)
    time.sleep(0.05)
    play_tone(659, 0.2)


# Clear heap space
gc.collect()

# Initialize directly at the matched 320x240 geometry floor
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

# Track paddle position with float for smoother movement
paddle_pos_x = 0.0

def handle_gamepad_press(key)-> tuple:
    global key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop
    
    # --- HARDWARE ALIGNMENT INJECTION ---
    # Map your physical controller numbers directly to standard game action scopes
    HW_RIGHT = 0   # Your D-pad right key register
    HW_LEFT = 1    # Your D-pad left key register
    HW_SELECT = 9  # Your SELECT button register
    HW_START = 8   # Your START button register
    # ------------------------------------

    if key in GAMEPAD_MAP:
        if key == HW_LEFT or key == relic_usb_host_gamepad.BUTTON_Y or key == relic_usb_host_gamepad.BUTTON_B or key == relic_usb_host_gamepad.BUTTON_L1:
            if my_debug:
                print("Left pressed")
            key_left_pressed = True
        elif key == HW_RIGHT or key == relic_usb_host_gamepad.BUTTON_X or key == relic_usb_host_gamepad.BUTTON_A or key == relic_usb_host_gamepad.BUTTON_R1:
            if my_debug:
                print("Right pressed")
            key_right_pressed = True
        elif key == HW_SELECT:
            if my_debug:
                print("Space pressed")
            key_space_pressed = True
        elif key == HW_START:
            if my_debug:
                print("Start (= Exit game) pressed")
            lStop = True  # We're out of here
    else:
        print(f"unhandled key: \"{key}\"")

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
            print("Input error:", e)

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
    controls_label = label.Label(
        terminalio.FONT,
        text="A: Left   D: Right",
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

def reset_ball():
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
reset_ball()

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

if my_debug:
    print(f"Waiting for {k_lbl} press to start the game")

while True:
    current_time = time.monotonic()
    
    # Check keyboard input
    # key_left_pressed, key_right_pressed, key_space_pressed, any_key = check_keys()
    if use_keyboard:
        # Check keyboard input
        key_left_pressed, key_right_pressed, key_space_pressed, any_key = check_keys()
    elif use_gamepad:
        try:
            if gamepad and gamepad.update():
                for event in gamepad.events:
                    # 1. Handle the Menu-Start button bypass cleanly
                    if lStart:
                        if event.key_number == 8 or event.key_number == 7: # Check both Select/Start clone pins
                            if my_debug:
                                print(f"Gamepad button {event.key_number} bypassed to prevent menu click-through.")
                            lStart = False
                            # Force-drain everything currently waiting in the gamepad collection queues
                            
                            # Safely exhaust all elements in the tuple buffer to drain it completely
                            for _ in gamepad.events:
                                pass
                        continue # Safely drain this frame's initialization token

                    # 2. Process real in-game movements when pressed
                    if event.pressed:
                        last_interaction_time = time.monotonic()
                        
                        # FIX: Assign directly to the variable names your physics framework checks!
                        # If your game checks 'key_left_pressed', use that here. If it checks 'left_pressed', match it!
                        key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop = handle_gamepad_press(event.key_number)
                        
                        elapsed_time = last_interaction_time - start_time
                        start_time = time.monotonic()
                        if my_debug:
                            print(f"Elapsed time since last interaction: {elapsed_time:.2f} seconds")
                            
        except KeyboardInterrupt:
            break

    elif use_mouse:
        pass

    if lStop:
        print("Exiting game loop.")
        update_message("Exiting game...")
        break
    
    # Apply paddle movement ONLY if keys are currently pressed
    if key_left_pressed and paddle_pos_x > 0:
        paddle_pos_x -= PADDLE_SPEED
        # Ensure paddle doesn't go offscreen
        if paddle_pos_x < 0:
            paddle_pos_x = 0

    if key_right_pressed and paddle_pos_x < display.width - PADDLE_WIDTH:
        paddle_pos_x += PADDLE_SPEED
        # Ensure paddle doesn't go offscreen
        if paddle_pos_x > display.width - PADDLE_WIDTH:
            paddle_pos_x = display.width - PADDLE_WIDTH

    # Update paddle position with integer conversion
    paddle.x = int(paddle_pos_x)

    # Handle space bar for start/launch with debouncing
    if key_space_pressed and key_space_released:
        key_space_released = False  # Prevent multiple triggers until released

        if game_over:
            # Reset everything for a new game
            (main_group, paddle, ball, bricks, score_label,
             lives_label, message_label, controls_label) = create_game_elements()
            display.root_group = main_group
            score = 0
            lives = 3
            brick_count = BRICK_ROWS * BRICK_COLS
            game_over = False
            reset_ball()
            update_message("")
            # Reset paddle position tracker
            paddle_pos_x = float((display.width - PADDLE_WIDTH) // 2)

            # Play restart sound
            play_game_start()

        if not game_active and not game_over:
            game_active = True
            launch_ball()
            update_message("")

            # Play ball launch sound
            play_tone(587, 0.1)  # D5, short

    # Reset space key released state if no key is pressed
    if not key_space_pressed:
        key_space_released = True

    # Handle game logic when active
    if game_active and not game_over:
        # Update ball position (using float variables first)
        ball_pos_x += ball_dx
        ball_pos_y += ball_dy
        # Update the actual ball object with integer positions
        ball.x = int(ball_pos_x)
        ball.y = int(ball_pos_y)

        # Ball collision with walls with sound
        wall_hit = False

        if ball_pos_x - BALL_RADIUS <= 0:
            ball_pos_x = BALL_RADIUS + 1  # Prevent sticking to wall
            ball_dx = abs(ball_dx)  # Move right
            wall_hit = True
        elif ball_pos_x + BALL_RADIUS >= display.width:
            ball_pos_x = display.width - BALL_RADIUS - 1  # Prevent sticking to wall
            ball_dx = -abs(ball_dx)  # Move left
            wall_hit = True

        if ball_pos_y - BALL_RADIUS <= 0:
            ball_pos_y = BALL_RADIUS + 1  # Prevent sticking to wall
            ball_dy = abs(ball_dy)  # Move down
            wall_hit = True

        # Play wall hit sound with cooldown to prevent sound overlap
        if wall_hit and current_time - last_wall_hit_time > sound_cooldown:
            play_wall_hit()
            last_wall_hit_time = current_time

        # Ball fell below paddle
        if ball_pos_y + BALL_RADIUS > display.height - DISPLAY_LINE:
            lives -= 1
            lives_label.text = f"Lives: {lives}"

            # Play life lost sound
            play_life_lost()

            if lives <= 0:
                game_active = False
                game_over = True
                update_message(f"GAME OVER - Press {k_lbl} to play again, Q to quit")

                # Play game over sound
                play_game_over()
            else:
                reset_ball()
                game_active = False
                update_message(f"Press {k_lbl} to continue")

        # Ball collision with paddle
        paddle_collision = (
            ball_pos_y + BALL_RADIUS >= paddle.y and
            ball_pos_y - BALL_RADIUS <= paddle.y + PADDLE_HEIGHT and
            ball_pos_x + BALL_RADIUS >= paddle.x and
            ball_pos_x - BALL_RADIUS <= paddle.x + PADDLE_WIDTH
        )

        if paddle_collision:
            # Determine bounce angle based on where ball hit paddle
            # Center of paddle gives straight bounce, edges give angled bounce
            hit_position = (ball_pos_x - paddle.x) / PADDLE_WIDTH
            angle_factor = 2 * (hit_position - 0.5)  # -1 to 1 based on position

            # Set new ball direction with slight speed increase
            ball_speed = min(ball_speed * 1.05, 4.5)  # Speed up slightly, max at 4.5
            ball_dx = ball_speed * angle_factor
            # Ensure upward movement
            ball_dy = -ball_speed * (1 - 0.8 * abs(angle_factor))

            # Ensure ball is above paddle (prevent sticking)
            ball_pos_y = paddle.y - BALL_RADIUS - 1
            ball.y = int(ball_pos_y)

            # Play paddle hit sound
            play_paddle_hit()

        # Ball collision with bricks
        for brick in bricks:
            brick_collision = (
                brick in main_group and
                brick.x <= ball_pos_x + BALL_RADIUS and
                brick.x + BRICK_WIDTH >= ball_pos_x - BALL_RADIUS and
                brick.y <= ball_pos_y + BALL_RADIUS and
                brick.y + BRICK_HEIGHT >= ball_pos_y - BALL_RADIUS
            )

            if brick_collision:
                # Skip if this is the same brick we just hit (prevent double hits)
                if brick == last_hit_brick:
                    continue

                last_hit_brick = brick
                main_group.remove(brick)
                brick_count -= 1

                # Determine which side of the brick was hit
                dx1 = ball_pos_x - brick.x  # Distance from left edge
                dx2 = brick.x + BRICK_WIDTH - ball_pos_x  # Distance from right edge
                dy1 = ball_pos_y - brick.y  # Distance from top edge
                dy2 = brick.y + BRICK_HEIGHT - ball_pos_y  # Distance from bottom edge

                # Find the minimum distance
                min_dist = min(dx1, dx2, dy1, dy2)

                # Bounce based on which side was hit
                if min_dist in (dy1, dy2):  # Top or bottom hit
                    ball_dy = -ball_dy
                else:  # Left or right hit
                    ball_dx = -ball_dx

                # Update score
                score += 10
                score_label.text = f"Score: {score}"

                # Play brick hit sound
                play_brick_hit()

                # Check win condition
                if brick_count <= 0:
                    game_active = False
                    game_over = True
                    update_message(f"YOU WON! Press {k_lbl} to play again")

                    # Play victory sound
                    play_level_win()

                # Only process one brick collision per frame
                break

        # Reset last_hit_brick if we're not touching it anymore
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
        # Ball sticks to paddle when not active
        ball.x = paddle.x + PADDLE_WIDTH // 2
        ball_pos_x = float(ball.x)

    # Refresh display
    display.refresh()
    time.sleep(0.016)  # ~60fps
