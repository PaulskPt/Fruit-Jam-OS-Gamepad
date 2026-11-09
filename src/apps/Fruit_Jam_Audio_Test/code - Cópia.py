# SPDX-FileCopyrightText: 2026 PaulskPt & Gemini
# SPDX-License-Identifier: MIT
# Audio Test Utility for FruitJam (RP2350B) - Hardware Reset Fix
# See: https://learn.adafruit.com/adafruit-fruit-jam/fruit-jam-library
import sys
import time
import math
import array
import audiocore
import synthio
import gc
import board
import digitalio
import displayio
import supervisor
#import neopixel
from adafruit_fruitjam.peripherals import Peripherals
from launcher_config import LauncherConfig

my_debug = False

# 1. Generate a mathematically smooth 16-bit sine wave table
SAMPLE_SIZE = 512
sine_table = array.array("h", [0] * SAMPLE_SIZE)
for idx in range(SAMPLE_SIZE):
    sine_table[idx] = int(math.sin(math.pi * 2 * idx / SAMPLE_SIZE) * 32767)

# 2. Create a smooth volume envelope to eliminate the clicking/popping
# Place this here globally!
note_envelope = synthio.Envelope(
    attack_time=0.02,
    decay_time=0.0,
    sustain_level=1.0,
    release_time=0.05
)

path_name = "F:/CIRCUITPY/apps/"
game_name = "Fruitjam_Audio_Test"
fn = "code.py"

launcher_config = LauncherConfig()
use_sound = False

my_debug =  launcher_config.data.get("my_debug", False)  # override the definition above
if my_debug:
    print(f"my_debug from launcher_conf.json = {my_debug}")
use_gamepad = launcher_config.data.get("use_gamepad", True)
use_keyboard = launcher_config.data.get("use_keyboard", False)
use_sound = launcher_config.data.get("use_sound", True)
audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")
has_gamepad = None
gamepad = None

key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_start_pressed = False
key_start_released = True
key_space_released = True  # Track space key release to prevent multiple actions
any_key = False  # --- ADD This line to fix the function lookup crash! ---
k_lbl = None

lStart = True
lStop = False

use_neopixels = True
BLINK_ALL_NEOPIXELS = 100

fruitjam = Peripherals()
fruitjam.neopixels.brightness = 0.1

# --- HARDWARE ALIGNMENT INJECTION ---
# Map your physical controller numbers directly to standard game action scopes
HW_LEFT   = 6  # Your D-pad left key register
HW_RIGHT  = 7 # Your D-pad right key register
HW_START  = 8  # Your START button register
HW_SELECT = 9  # Your SELECT button register
# ------------------------------------

start_time = time.monotonic()  # Track start time for potential future use (e.g., timing events)
interval_time = 0.1 # Time interval for checking inputs and updating game state (can be adjusted for performance)
elapsed_time = 0
last_interaction_time = start_time
sound_cooldown= 0.05

def ck_stop_button():
    """
    Reads on-board button #1 via the library's proper button1 naming. 
    Updates the global lStop flag to True when pressed.
    """
    global lStop
    # The library handles pull-ups internally and returns True when pressed!
    if fruitjam is not None and hasattr(fruitjam, 'button1'):
        if fruitjam.button1:
            if my_debug: print("On-board Button 1 pressed! Stopping...")
            lStop = True

def blink_neopixels(LED_NR: int):
    """
    Blinks NeoPixel LED #1 green using the library pixel array wrapper.
    """
    txt0 = "blink_neopixels(): "
    txt1 = "blinking neopixel led"
    blink_all = False
    
    if LED_NR != BLINK_ALL_NEOPIXELS:
        if LED_NR < 0:
            LED_NR = 0 # Blink all leds
        elif LED_NR > 5:
            LED_NR = 5
    
    GREEN = (0, 255, 0)
    OFF = (0, 0, 0)
    
    if my_debug:
        if LED_NR == BLINK_ALL_NEOPIXELS:
            print(f"{txt0}{txt1} ALL")
        else: 
            print(f"{txt0}{txt1} nr: {LED_NR}")
    
    if fruitjam is None:
        print(f"{txt0} type(fruitjam) = {type(fruitjam)}")
        return
    
    if fruitjam.neopixels is None: 
        print(f"{txt0} type(pixels = {type(fruitjam.neopixels)}")
        return
    
    for _ in range(2):
        # 1. Turn the array green and force update
        if LED_NR == BLINK_ALL_NEOPIXELS:
            # All five leds
            fruitjam.neopixels.fill(GREEN)
            fruitjam.neopixels.show()
        elif LED_NR in [0, 1, 2, 3, 4]:
            fruitjam.neopixels[LED_NR] = GREEN
            fruitjam.neopixels.show()
        time.sleep(0.15)
        
        # 2. Turn it off and force update
        if LED_NR == BLINK_ALL_NEOPIXELS:
            fruitjam.neopixels.fill(OFF)
            fruitjam.neopixels.show()
        elif LED_NR in [0, 1, 2, 3, 4]:
            fruitjam.neopixels[LED_NR] = OFF
            fruitjam.neopixels.show()
        time.sleep(0.15)

def flush_gamepad_events(timeout=0.2):
    """Drains the gamepad queue with a safety timeout guard."""
    if gamepad is not None:
        start_time = time.monotonic()
        while gamepad.update():
            for event in gamepad.events:
                pass
            # Safety exit if buttons are actively being held down
            if time.monotonic() - start_time > timeout:
                break


# Dummy function
def ck_keys():
    pass

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

def play_note(frequency, duration):
    """Plays a note cleanly with an envelope to eliminate tail clicks."""
    test_note.frequency = int(frequency)
    
    # Start playing the note (executes the 0.02s fade-in)
    synth.press(test_note)            

    # Hold the note down for the main duration minus the fade-out cushion
    # (0.05s release cushion prevents clipping before synth.release)
    hold_duration = max(0.01, duration - 0.05)
    start_time = time.monotonic()
    while time.monotonic() - start_time < hold_duration:
        pass                          

    # Tell the note to start its smooth 0.05s fade-out sequence
    synth.release(test_note)          

    # Allow the hardware 0.05s to finish playing the fade-out tail
    start_time = time.monotonic()
    while time.monotonic() - start_time < 0.05:
        pass


def handle_gamepad_press(key, is_pressed) -> tuple:
    global key_left_pressed, key_right_pressed, key_space_pressed, any_key, key_start_pressed, lStop
    
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
            key_start_pressed = True
            lStop = True  # We're out of here
    else:
        if not my_debug:
            print(f"unhandled key: \"{key}\"")
        else:
            pass

    return (key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop)

def ck_gamepad() -> bool:
    global lStart, lStop, any_key, key_left_pressed, key_right_pressed, key_space_pressed, key_start_pressed
    global start_time, last_interaction_time, last_wall_hit_time, sound_cooldown
    my_ret = False
    start_time = time.monotonic()
    if use_gamepad:
        while True:
            try:
                if gamepad and gamepad.update():
                    for event in gamepad.events:
                        # --- ADD THIS RAW CODES MONITOR LINE ---
                        if my_debug:
                            print(f"RAW CONTROLLER PACKET -> Key Number: {event.key_number} | Pressed State: {event.pressed}")
                        # --------------------------------------
                    
                        # This single line handles both press (True) and release (False) beautifully!
                        key_left_pressed, key_right_pressed, key_space_pressed, any_key, lStop = handle_gamepad_press(event.key_number, event.pressed)
                        
                        last_interaction_time = time.monotonic()
                        interval_time = last_interaction_time - start_time
                        if interval_time > 3:
                            print(f"ck_gamepad() timed-out. Exiting...")
                            break
                        
                        if key_left_pressed or key_right_pressed or key_space_pressed or any_key or lStop:
                            my_ret = True
                            break
                else:
                    break
                 
            except KeyboardInterrupt:
                my_ret = False
                break
    
    return my_ret


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


if my_debug:
    print("Flushing lingering gamepad events from menu launcher...")
flush_gamepad_events()

print("Initializing FruitJam audio subsystem...")

# Initialize audio output
if use_sound:
    print("Initializing FruitJam audio subsystem...")
    if fruitjam.dac is None:
            print("\nAre you running this on a Fruit Jam?")
            sys.exit(1)
    
    print(f"Audio output configuration: {audio_output_fm_config}")
        
    if audio_output_fm_config == "headphone":
        fruitjam.dac.headphone_output = True
        fruitjam.dac.speaker_output = False
    elif audio_output_fm_config == "speaker":
        fruitjam.dac.speaker_output = True
        fruitjam.dac.headphone_output = False
        
    # Safely route to your speaker configuration settings via properties
    #fruitjam.audio_output = audio_output_fm_config 
    #fruitjam.dac.speaker_output = True
    
    fruitjam.dac.dac_volume = 0         # Digital volume (-63.5 to 24.0 dB)
    fruitjam.dac.speaker_volume = 8    # Analog volume (-78.3 to 0 dB)
    fruitjam.dac.speaker_gain = 24      # Amplifier gain (6, 12, 18, or 24 dB)
    # Set the safe library master float volume property
    fruitjam.volume = 0.70
    
    # 4. Safety verification printout for register states
    print(f"DAC Speaker Output state: {fruitjam.dac.speaker_output}")
    print(f"DAC Speaker Gain: {fruitjam.dac.speaker_gain} dB")

    # Attach the background hardware Synthesizer engine
    gc.collect()
    synth = synthio.Synthesizer(sample_rate=fruitjam.dac.sample_rate, channel_count=1)

    fruitjam.audio.stop()
    time.sleep(0.01)
    fruitjam.audio.play(synth)

    # 1. Initialize cleanly using standard library defaults
    # fruitjam = Peripherals(safe_volume_limit=0.75)

    if fruitjam.dac is None:
        print("DAC Initialization failed!")
        sys.exit(1)

    # 2. Use high-level library property to switch routing profile safely
    # This automatically flags speaker output and configures internal registers
    fruitjam.audio_output = audio_output_fm_config 

    # 3. Explicitly set volume using the high-level float property (0.0 to 1.0)
    # The default volume can sometimes initialize near absolute zero
    fruitjam.volume = 0.70  

    # --- Attach the background hardware Synthesizer engine ---
    gc.collect()
    synth = synthio.Synthesizer(sample_rate=fruitjam.dac.sample_rate, channel_count=1)

    fruitjam.audio.stop()
    time.sleep(0.01)
    fruitjam.audio.play(synth)

    # Define a reusable note container
    # test_note = synthio.Note(frequency=440)
    test_note = synthio.Note(frequency=440, waveform=sine_table, envelope=note_envelope)

    # Play a bright ascending arpeggio (C5 -> E5 -> G5)
    notes2 = [523, 659, 784] # C5, E5, G5
    name2 = ["C5", "E5", "G5"]
    duration2 = [0.60, 0.65, 0.70]

    nr_of_times = 5
    sleep_t = 0.15
    result = False 
    
    #for i in range(nr_of_times):
    i = 0
    while True:
        print(f"Run {i+1}")
        for j in range(len(notes2)):
            print(f"Going to play note: {notes2[j]} Hz (= \"{name2[j]}\") for {duration2[j]:.2f} Sec")
            time.sleep(sleep_t)
            play_note(notes2[j], duration2[j])   
            time.sleep(sleep_t)
            
        # 1. Check the on-board button every single run loop iteration
        ck_stop_button()
        
        # 2. Check alternative inputs
        if use_keyboard:
            ck_keys()
        elif use_gamepad:
            result = ck_gamepad()
            print(f"result of ck_gamepad() = {"True" if result else "False"}. Value lStop = {"True" if lStop else "False"}")

        # 3. If either input flipped lStop to True, trigger the clean fade out and exit
        if lStop:
            print("Stop signal caught! Fading out audio...")
            # Flash the NeoPixel green right before reloading
            # print("Calling blink_neopixels()...")
            blink_neopixels(4) # Use BLINK_ALL_NEOPIXELS or a value in [0, 1, 2, 3, 4]
            
            current_vol = fruitjam.volume
            while current_vol > 0.0:
                current_vol -= 0.05
                if current_vol < 0: current_vol = 0
                fruitjam.volume = current_vol
                time.sleep(0.01)
            
            synth.release_all()
            fruitjam.audio.stop()
            break

        time.sleep(2)
        i += 1
        if i > 100:
            i = 0


    print("\nDONE!\n")
    print("Please release all gamepad buttons to return to the menu...")

    # FIX: Force-drain the USB stack and wait until no buttons are being held down
    try:
        import relic_usb_host_gamepad
        test_gamepad = relic_usb_host_gamepad.Gamepad()

        # Run a loop for up to 5 seconds or until the button queue is cleared out
        start_flush = time.monotonic()
        while time.monotonic() - start_flush < 5.0:
            if test_gamepad.update():
                # If we find any events, read through them to empty the hardware cache
                for event in test_gamepad.events:
                    pass

            # Give the processor a microsecond break to let the USB host update its states
            time.sleep(0.05)
    except ImportError:
        pass

print("Exiting app and returning to launcher cleanly...\n\n")
time.sleep(1)

# Force a graceful system reload back to the clean menu state
supervisor.reload()
