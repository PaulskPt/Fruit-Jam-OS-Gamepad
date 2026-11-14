# SPDX-FileCopyrightText: 2026 Paulus Schulinck (Github @PaulskPt)
# SPDX-License-Identifier: MIT
# Created with help of Google AI
# This script makes uUse of an external SNES type gamepad controller and an external speaker
import sys
import time
import gc
import board # type: ignore
import synthio # type: ignore
import atexit
import supervisor # type: ignore
from adafruit_fruitjam.peripherals import Peripherals # type: ignore
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    SELECT_BUTTONS,
    START_BUTTONS,
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
    Y_BUTTONS,
    X_BUTTONS
)

my_debug = False

use_sound = True
use_headphone = False
use_speaker = True
fruitjam = None
audio_output_fm_config = None

# path_name = "F:/CIRCUITPY/apps/"
game_name = "Fruit_Jam_Synthio_Test"
# fn = "code.py"

# Input state
Stop = False
key_left_pressed = False
key_right_pressed = False

launcher_config = LauncherConfig()
my_debug = launcher_config.data.get("my_debug", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)
audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")

if use_sound:
    launcher_config.audio_output = audio_output_fm_config

# Initialize shared GamepadManager (Only ONCE at startup)
pad = None
if use_gamepad:
    """ Create the pad object """
    pad = GamepadManager(check_bridge=True, debug=my_debug)
    if pad.connected:
        pad.print_controls("Synthio Test", (
            ("L1 / R1", "Dec/Increase notes group index"),
            ("START  ", "Exit to main menu"),
        ))
        pad.wait_for_release(min_drain=0.25, timeout=1.5)
    else:
        print(f"{game_name}No gamepad connected. Exiting...")
        Stop = True

if launcher_config.audio_output == "headphone":
    use_headphone = True
    use_speaker = False
else:
    use_headphone = False
    use_speaker = True

""" Create the fruitjam object """
fruitjam = Peripherals(audio_output="speaker" if not use_headphone else "headphone", safe_volume_limit=1.0 if not use_headphone else 0.75)

fruitjam.dac.speaker_output = use_speaker
fruitjam.dac.headphone_output = use_headphone

if use_speaker:
    fruitjam.dac.speaker_volume = 0   # 0 dB is max unattenuated digital volume

TARGET_SAMPLE_RATE = 22050
fruitjam.dac.configure_clocks(sample_rate=TARGET_SAMPLE_RATE, bit_depth=16)
time.sleep(0.35)

audio_stream = fruitjam.audio
synth = synthio.Synthesizer(sample_rate=TARGET_SAMPLE_RATE)
audio_stream.play(synth)
print("Audio clock stream verified and active.")

BLINK_ALL_NEOPIXELS = 100

fruitjam.neopixels.brightness = 0.1

GREEN = (0,   255, 0)
RED   = (255,   0, 0)
OFF   = (0,     0, 0)

def blink_neopixels(LED_NR: int, COLOR: tuple):
    """Blinks NeoPixel LED green using the library pixel array wrapper."""
    txt0 = "blink_neopixels(): "
    txt1 = "blinking neopixel led"

    if LED_NR != BLINK_ALL_NEOPIXELS:
        if LED_NR < 0:
            LED_NR = 0
        elif LED_NR > 5:
            LED_NR = 5

    if not COLOR in [GREEN, RED, OFF]:
        print(f"Undefined color tuple: {COLOR}")
        return

    if my_debug:
        if LED_NR == BLINK_ALL_NEOPIXELS:
            print(f"{txt0}{txt1} ALL")
        else:
            print(f"{txt0}{txt1} nr: {LED_NR}")

    if fruitjam is None or fruitjam.neopixels is None:
        return

    for _ in range(2):
        # 1. Turn the array green and force update
        if LED_NR == BLINK_ALL_NEOPIXELS:
            # All five leds
            fruitjam.neopixels.fill(COLOR)
            fruitjam.neopixels.show()
        elif LED_NR in [0, 1, 2, 3, 4]:
            fruitjam.neopixels[LED_NR] = COLOR
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


def ck_pad():
    """Non-blocking update loop to query the shared pad button state."""
    global key_left_pressed, key_right_pressed, Stop
    #if use_gamepad and pad and pad.connected:
    pad.update()
    
    if pad.is_any_just_pressed(START_BUTTONS):
        Stop = True
        return

    if pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS): 
        key_left_pressed = True
        return

    if pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
        key_right_pressed = True
        return


def run_synthio_test():
    global Stop, key_left_pressed, key_right_pressed
    
    if Stop: # See the pad.connected() above
        return
    
    if my_debug:
        print("Starting locked chord loop with NeoPixel animations. Press START to exit.")
    
    notes_dict = {0: [60, 64, 67],
                  1: [70, 74, 78],
                  2: [83, 86, 90]}
    
    notes = None
    notes_idx = 0
    notes_idx_old = 0
    notes_idx_min = 0
    notes_idx_max = len(notes_dict) - 1
    note_duration = 0.5

    while True:
        try:
            # 1. Fetch the list of 3 notes matching the locked dictionary key
            notes = notes_dict[notes_idx]

            # 2. Iterate sequentially through each note in the current group
            for midi_note in notes:
                note_obj = synthio.Note(frequency=synthio.midi_to_hz(midi_note), amplitude=1.0)
                synth.press(note_obj)
                
                time.sleep(note_duration)
                # 3. Release the active note cleanly
                synth.release(note_obj)
                
                # 4. Brief inter-note pause within the active group cycle
                time.sleep(0.15)

            """ 
                At 'expense' of button reaction time but in favor of clean notes
                we only call ck_pad() after finishing the sequence of three notes
            """
            ck_pad()
            # Escape the sequence loop immediately if an event flag was raised
            if Stop:
                print("START pressed: exiting...")
                blink_neopixels(4, RED) 
                break

            # 6. Handle all state logic cleanly outside the 3-note cycle loop
            if key_left_pressed:
                key_left_pressed = False
                notes_idx -= 1
                if notes_idx < notes_idx_min:
                    notes_idx = notes_idx_max

            if key_right_pressed:
                key_right_pressed = False
                notes_idx += 1
                if notes_idx > notes_idx_max:
                    notes_idx = notes_idx_min

            # When cycle finished, check if other notes list has to be used
            if notes_idx != notes_idx_old:
                blink_neopixels(notes_idx, GREEN)  # blink led 0, 1 or 2 in GREEN color
                notes_idx_old = notes_idx
                if not my_debug:
                    print(f"notes_idx changed to: {notes_idx}")

                if notes_idx in notes_dict.keys():
                    notes = notes_dict[notes_idx]
                else:
                    notes = notes_dict[0]  # default

                # Strike the first note of the newly selected group immediately
                continue

        except KeyboardInterrupt:
            print("KeyboardInterrupt: exiting...")
            Stop = True
            audio_stream.stop()

        # The exit check handles both pad button quits and KeyboardInterrupts seamlessly here
        if Stop:
            blink_neopixels(4, RED)  # blink led 4 in RED color
            break  # break from while loop


def atexit_callback():
    print("inside atexit callback")
    if pad is not None:
        pad.release()
    try:
        from adafruit_argv_file import write_argv  # type: ignore
        write_argv(__file__, [])
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
    try:
        run_synthio_test()
    except Exception as err:
        import traceback
        traceback.print_exception(err)
        time.sleep(5)
    finally:
        if Stop:
            Stop = False # Reset the global Stop flag
            supervisor.reload()
        else:
            while True:
                time.sleep(1)
