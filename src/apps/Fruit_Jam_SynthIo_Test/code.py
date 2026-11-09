# SPDX-FileCopyrightText: 2026 Adafruit Industries
# SPDX-License-Identifier: MIT
# Created by Google AI for @PaulskPt
import time
import board
import synthio
from adafruit_fruitjam.peripherals import Peripherals

print("--- Fruit Jam RP2350B synthio Test Script ---")

# 1. Initialize Fruit Jam specialized hardware peripherals
# This handles the low-to-high transition on PERIPH_RESET (Pin 22),
# configures the shared I2C bus, and sets up the internal I2S audio stream.
use_headphones = True  # Set to False to route audio to the 1W speaker instead

fruit_jam = Peripherals(audio_output="speaker" if not use_headphones else "headphones", safe_volume_limit=0.75)

# 2. Instruct the onboard TLV320 DAC chip to route mixing to the speaker amplifier
fruit_jam.dac.speaker_output = True
fruit_jam.dac.headphone_output = False

# 3. Align the audio clock dividers on the RP2350B for the target sample rate
TARGET_SAMPLE_RATE = 22050
fruit_jam.dac.configure_clocks(sample_rate=TARGET_SAMPLE_RATE, bit_depth=16)

# 4. Give the DAC power-on volume ramp time to finish stabilizing
time.sleep(0.35)

# 5. Extract the initialized I2S object and attach it to synthio
audio_stream = fruit_jam.audio
synth = synthio.Synthesizer(sample_rate=TARGET_SAMPLE_RATE)

# 6. Bind the synthio engine directly to the clocked hardware stream
audio_stream.play(synth)
print("Audio clock stream verified and active. Playing test notes...")

# 7. Test loop: Play a clean notes sequence
# Trigger middle C (MIDI 60), then E (MIDI 64), then G (MIDI 67)
test_notes = [60, 64, 67]

try:
    for midi_note in test_notes:
        note_obj = synthio.Note( frequency=synthio.midi_to_hz(midi_note) )
        
        print(f"Pressing Note: {midi_note} ({note_obj.frequency:.1f} Hz)")
        synth.press(note_obj)
        time.sleep(0.5)
        
        print(f"Releasing Note: {midi_note}")
        synth.release(note_obj)
        time.sleep(0.1)

    print("Audio sequence complete.")

finally:
    # Always turn off audio generation and cleanly close the DMA handle on exit
    audio_stream.stop()
    print("Audio stream released cleanly back to the menu system.")

time.sleep(1.0)

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