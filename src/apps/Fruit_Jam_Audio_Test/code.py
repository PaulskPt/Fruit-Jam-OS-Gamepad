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
import supervisor
from adafruit_fruitjam.peripherals import Peripherals
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    LEFT_BUTTONS,
    RIGHT_BUTTONS,
    SELECT_BUTTONS,
    START_BUTTONS,
)

my_debug = False

# 1. Generate a mathematically smooth 16-bit sine wave table
SAMPLE_SIZE = 512
sine_table = array.array("h", [0] * SAMPLE_SIZE)
for idx in range(SAMPLE_SIZE):
    sine_table[idx] = int(math.sin(math.pi * 2 * idx / SAMPLE_SIZE) * 32767)

# 2. Create a smooth volume envelope to eliminate clicking/popping
note_envelope = synthio.Envelope(
    attack_time=0.02,
    decay_time=0.0,
    sustain_level=1.0,
    release_time=0.05,
)

path_name = "F:/CIRCUITPY/apps/"
game_name = "Fruitjam_Audio_Test"
fn = "code.py"

launcher_config = LauncherConfig()

my_debug = launcher_config.data.get("my_debug", False)
if my_debug:
    print(f"my_debug from launcher_conf.json = {my_debug}")
use_gamepad = launcher_config.data.get("use_gamepad", True)
use_keyboard = launcher_config.data.get("use_keyboard", False)
use_sound = launcher_config.data.get("use_sound", True)
audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")

key_left_pressed = False
key_right_pressed = False
key_space_pressed = False
key_start_pressed = False
any_key = False

lStart = True
lStop = False

use_neopixels = True
BLINK_ALL_NEOPIXELS = 100

fruitjam = Peripherals()
fruitjam.neopixels.brightness = 0.1

start_time = time.monotonic()
interval_time = 0.1
elapsed_time = 0
last_interaction_time = start_time
sound_cooldown = 0.05


def ck_stop_button():
    """Reads on-board button #1 and sets lStop to True when pressed."""
    global lStop
    if fruitjam is not None and hasattr(fruitjam, "button1"):
        if fruitjam.button1:
            if my_debug:
                print("On-board Button 1 pressed! Stopping...")
            lStop = True


def blink_neopixels(LED_NR: int):
    """Blinks NeoPixel LED green using the library pixel array wrapper."""
    txt0 = "blink_neopixels(): "
    txt1 = "blinking neopixel led"

    if LED_NR != BLINK_ALL_NEOPIXELS:
        if LED_NR < 0:
            LED_NR = 0
        elif LED_NR > 5:
            LED_NR = 5

    GREEN = (0, 255, 0)
    OFF = (0, 0, 0)

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


def ck_keys():
    pass


def play_tone(frequency, duration, volume=0.5):
    """Play a tone at the specified frequency for the specified duration."""
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


def play_note(frequency, duration):
    """Plays a note cleanly with an envelope to eliminate tail clicks."""
    test_note.frequency = int(frequency)
    synth.press(test_note)

    hold_duration = max(0.01, duration - 0.05)
    t0 = time.monotonic()
    while time.monotonic() - t0 < hold_duration:
        pass

    synth.release(test_note)

    t0 = time.monotonic()
    while time.monotonic() - t0 < 0.05:
        pass


def ck_gamepad() -> bool:
    """Poll shared GamepadManager and update input flags."""
    global lStop, any_key, key_left_pressed, key_right_pressed, key_space_pressed, key_start_pressed
    global last_interaction_time

    if not use_gamepad or pad is None or not pad.connected:
        return False

    raw_events = pad.update()
    if raw_events:
        last_interaction_time = time.monotonic()

    key_left_pressed = pad.is_any_held(LEFT_BUTTONS)
    key_right_pressed = pad.is_any_held(RIGHT_BUTTONS)
    key_space_pressed = pad.is_any_held(SELECT_BUTTONS)

    if pad.is_any_just_pressed(START_BUTTONS):
        if my_debug:
            print("Start (= Exit app) pressed")
        key_start_pressed = True
        lStop = True

    any_key = bool(raw_events) or key_left_pressed or key_right_pressed or key_space_pressed or lStop
    return any_key


# Initialize shared GamepadManager and drain any leftover launcher button press
pad = None
if use_gamepad:
    pad = GamepadManager(check_bridge=True, debug=my_debug)
    if pad.connected:
        if my_debug:
            print("Flushing lingering gamepad events from menu launcher...")
        pad.wait_for_release()
    elif not my_debug:
        print("Audio_Test: No gamepad flagged by launcher. Falling back to alternative inputs.")
        
    pad.print_controls("Audio Test", (
        ("START", "Stop audio & exit to menu"),
    ))

print("Initializing FruitJam audio subsystem...")

if use_sound:
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

    fruitjam.audio_output = audio_output_fm_config
    fruitjam.dac.dac_volume = 0
    fruitjam.dac.speaker_volume = 8
    fruitjam.dac.speaker_gain = 24
    fruitjam.volume = 0.70

    print(f"DAC Speaker Output state: {fruitjam.dac.speaker_output}")
    print(f"DAC Speaker Gain: {fruitjam.dac.speaker_gain} dB")

    gc.collect()
    synth = synthio.Synthesizer(sample_rate=fruitjam.dac.sample_rate, channel_count=1)

    fruitjam.audio.stop()
    time.sleep(0.01)
    fruitjam.audio.play(synth)

    test_note = synthio.Note(frequency=440, waveform=sine_table, envelope=note_envelope)

    # Play a bright ascending arpeggio (C5 -> E5 -> G5)
    notes2 = [523, 659, 784]
    name2 = ["C5", "E5", "G5"]
    duration2 = [0.60, 0.65, 0.70]

    sleep_t = 0.15
    i = 0

    while True:
        print(f"Run {i + 1}")
        for j in range(len(notes2)):
            print(f"Going to play note: {notes2[j]} Hz (= \"{name2[j]}\") for {duration2[j]:.2f} Sec")
            time.sleep(sleep_t)
            play_note(notes2[j], duration2[j])
            time.sleep(sleep_t)

            # Check stop inputs between notes too so START responds promptly
            ck_stop_button()
            if use_gamepad:
                ck_gamepad()
            if lStop:
                break

        if not lStop:
            ck_stop_button()
            if use_keyboard:
                ck_keys()
            elif use_gamepad:
                result = ck_gamepad()
                print(f"result of ck_gamepad() = {'True' if result else 'False'}. Value lStop = {'True' if lStop else 'False'}")

        if lStop:
            print("Stop signal caught! Fading out audio...")
            blink_neopixels(4)

            current_vol = fruitjam.volume
            while current_vol > 0.0:
                current_vol -= 0.05
                if current_vol < 0:
                    current_vol = 0
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

if pad is not None and pad.connected:
    print("Please release all gamepad buttons to return to the menu...")
    pad.wait_for_release(min_drain=0.2, timeout=3.0)
    pad.release()

print("Exiting app and returning to launcher cleanly...\n\n")
supervisor.set_next_code_file(
    "/code.py",
    sticky_on_reload=False,
    reload_on_error=True,
    working_directory="/",
)
time.sleep(0.5)
supervisor.reload()
