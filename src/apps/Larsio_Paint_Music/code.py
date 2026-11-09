# SPDX-FileCopyrightText: 2025 John Park and Claude AI for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
Larsio Paint Music
Fruit Jam w mouse, HDMI, audio out
or Metro RP2350 with EYESPI DVI breakout and TLV320DAC3100 breakout on STEMMA_I2C,
pin D7 reset, 9/10/11 = BCLC/WSEL/DIN
Refactored teardown to use clean soft reload and shared fj_gamepad release
"""
# pylint: disable=invalid-name,too-few-public-methods,broad-except,redefined-outer-name

# Main application file for Larsio Paint Music

import time
import gc
import sys
import supervisor
import atexit
from sound_manager import SoundManager
from note_manager import NoteManager
from ui_manager import UIManager

AUDIO_OUTPUT = "i2s"  # Options: "pwm" or "i2s"


class MusicStaffApp:
    """Main application class that ties everything together"""

    def __init__(self, audio_output="pwm"):
        BPM = 120
        SECONDS_PER_BEAT = 60 / BPM
        SECONDS_PER_EIGHTH = SECONDS_PER_BEAT / 2

        gc.collect()

        print("Initializing sound manager...")
        self.sound_manager = SoundManager(
            audio_output=audio_output,
            seconds_per_eighth=SECONDS_PER_EIGHTH,
        )

        time.sleep(0.5)
        gc.collect()

        print("Initializing note manager...")
        self.note_manager = NoteManager(
            start_margin=25,
            staff_y_start=int(240 * 0.1),
            line_spacing=int((240 - int(240 * 0.1) - int(240 * 0.2)) * 0.95) // 8,
        )

        gc.collect()

        print("Initializing UI manager...")
        self.ui_manager = UIManager(self.sound_manager, self.note_manager)

    def run(self):
        """Set up and run the application"""
        print("Setting up display...")
        self.ui_manager.setup_display()

        time.sleep(0.5)
        gc.collect()

        if self.ui_manager.find_mouse():
            print("Mouse found successfully!")
        else:
            print("WARNING: Mouse not found.")
            print("The application will run, but mouse control may be limited.")

        self.ui_manager.main_loop()


if __name__ == "__main__":
    gc.collect()
    print("Starting Music Staff Application...")

    app = None

    def atexit_callback():
        """Clean up USB devices and point execution back to root Launcher."""
        print("inside atexit callback")

        if app is not None:
            ui = getattr(app, "ui_manager", None)
            if ui is not None:
                # Release shared GamepadManager if attached to ui_manager or input_handler
                pad = getattr(ui, "pad", None)
                if pad is not None:
                    pad.release()

                handler = getattr(ui, "input_handler", None)
                if handler is not None:
                    handler_pad = getattr(handler, "pad", None)
                    if handler_pad is not None:
                        handler_pad.release()

                    mouse = getattr(handler, "mouse", None)
                    if mouse is not None:
                        try:
                            mouse.release()
                            if getattr(mouse, "was_attached", False):
                                while supervisor.runtime.serial_bytes_available:
                                    sys.stdin.read(1)
                        except Exception as e:
                            print(f"Error releasing mouse: {e}")

        print("Pointing boot configuration back to root launcher...")
        supervisor.set_next_code_file(
            "/code.py",
            sticky_on_reload=False,
            reload_on_error=True,
            working_directory="/",
        )

    atexit.register(atexit_callback)

    try:
        print(f"trying start audio with AUDIO_OUTPUT= {AUDIO_OUTPUT}")
        app = MusicStaffApp(audio_output=AUDIO_OUTPUT)
    except Exception as e:
        print(f"Error with I2S audio: {e}")
        gc.collect()
        time.sleep(1)

        try:
            AUDIO_OUTPUT = "pwm"
            print(f"trying (fallback) start audio with AUDIO_OUTPUT= {AUDIO_OUTPUT}")
            app = MusicStaffApp(audio_output="pwm")
        except Exception as e2:
            print(f"Fatal audio error: {e2}")
            app = None
        
    if app is not None:
        try:
            app.run()
        except Exception as run_err:
            print(f"Runtime error: {run_err}")
            import traceback
            traceback.print_exception(run_err)
            time.sleep(5)

    supervisor.reload()
