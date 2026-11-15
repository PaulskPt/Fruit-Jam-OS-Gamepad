# Board: Adafruit Fruit Jam
# CircuitPython 10.1.4
# USB Gamepad style SNES test
# by Paulus Schulinck (Github handle: @PaulskPt)
# Copyright 2026
# License MIT
# Version 3

"""
Script REPL output:
/apps/SNES_gamepad_test/code.py output:
my_debug=    False
use_gamepad= True

--- SNES_gamepad_test SNES Gamepad Controls ---
  SELECT     : Start this test
  START      : Exit to main menu
------------------------------------------------

Press SELECT to begin the test.
Starting the SNES gamepad test.
is_pressed = True, key_num = 2
SECOND_GAMEPAD_MAP[2] = ['\x1b[X', 'Button X', 'Left']
is_pressed = True, key_num = 3
SECOND_GAMEPAD_MAP[3] = ['\x1b[Y', 'Button Y', 'Right']
is_pressed = True, key_num = 0
SECOND_GAMEPAD_MAP[0] = ['\x1b[A', 'Button A', 'Up']
is_pressed = True, key_num = 1
SECOND_GAMEPAD_MAP[1] = ['\x1b[B', 'Button B', 'Down']
is_pressed = True, key_num = 4
SECOND_GAMEPAD_MAP[4] = ['\x1b[a', 'D-Pad Up', 'Up']
is_pressed = True, key_num = 5
SECOND_GAMEPAD_MAP[5] = ['\x1b[b', 'D-Pad Down', 'Down']
is_pressed = True, key_num = 6
SECOND_GAMEPAD_MAP[6] = ['\x1b[d', 'D-Pad Left', 'Left']
is_pressed = True, key_num = 7
SECOND_GAMEPAD_MAP[7] = ['\x1b[c', 'D-Pad Right', 'Right']
is_pressed = True, key_num = 11
SECOND_GAMEPAD_MAP[11] = ['\x1b[5~', 'Button Left Shoulder', 'Left Shoulder']
is_pressed = True, key_num = 12
SECOND_GAMEPAD_MAP[12] = ['\x1b[6~', 'Button Right Shoulder', 'Right Shoulder']
is_pressed = True, key_num = 9
SECOND_GAMEPAD_MAP[9] = ['\x1b[E', 'Button Select', 'Select']
is_pressed = True, key_num = 8
SECOND_GAMEPAD_MAP[8] = ['\n', 'Button Start', 'Start']
START pressed. Exiting test in three seconds
inside atexit callback

Code done running.
soft reboot

"""

import time
import supervisor  # type: ignore
import atexit
from launcher_config import LauncherConfig
import gc 

from fj_gamepad import (
    GamepadManager,
    SECOND_GAMEPAD_MAP,
    SELECT_BUTTONS,
    START_BUTTONS)
#    SHOULDER_LEFT_BUTTONS,
#    SHOULDER_RIGHT_BUTTONS,
#    UP_BUTTONS,
#    DOWN_BUTTONS,
#    Y_BUTTONS,
#    X_BUTTONS
#)

my_debug = False
use_relic = True

#cur_page = 0
#index = None
#editor_index = None
gamepad = None
now = time.monotonic()

BTN_DPAD_UPDOWN_INDEX = 1
BTN_DPAD_LEFTRIGHT_INDEX = 0
BTN_ABXY_INDEX = 5
BTN_OTR_INDEX = 6

launcher_config = LauncherConfig()
my_debug = launcher_config.data.get("my_debug", False)
use_gamepad = launcher_config.data.get("use_gamepad", True)

print(f"my_debug=    {my_debug}")
print(f"use_gamepad= {use_gamepad}")

    
# Initialize shared GamepadManager (Only ONCE at startup)
pad = None
if use_gamepad:
    """ Create the pad object """
    pad = GamepadManager(check_bridge=True, debug=my_debug)
    if pad.connected:
        pad.print_controls("SNES_gamepad_test", (
            ("SELECT", "Start this test"),
            ("START ", "Exit to main menu"),
        ))
        pad.wait_for_release(min_drain=0.25, timeout=1.5)
        if my_debug:
            pad.print_second_map()
    else:
        print(f"{game_name}No gamepad connected. Exiting...")
        Stop = True


def handle_key_press(key):
    key_found = False
    # if my_debug:
    #     print(f"\nkey = {key}")
    if key in SECOND_GAMEPAD_MAP.keys():
        # if my_debug:
        #     print(f"key {key} found")
        v = SECOND_GAMEPAD_MAP[key]
        if my_debug:
            print(f"found gamepad event.key_number: {key:2d}. ANSI Escape code: {repr(v[0])} = \'{v[1]}\', button function: {v[2]}")
    else:
        if my_debug:
            print(f"unhandled key: \"{key}\"")
        else:
            pass

lStart = True
Stop = False

print("Press SELECT to begin the test.")

def run_SNES_gamepad_test():
    global lStart, Stop
    key_num = -1
    is_pressed = False
    
    while True:
        try:
            if pad:
                events = pad.update()
                if events:
                    if isinstance(events, list):
                        for event in events:
                            key_num = event[0]
                            is_pressed = event[1]
                            if my_debug:
                                # Print the raw tuple to see exactly what values are inside
                                print("Raw event tuple:", event) 
                                # Access elements by index if you know what they are
                                # e.g., if index 0 is the key number, and index 1 is the state:
                                # print(f"key_num {key_num}")
                                # print(f"is_pressd: {is_pressed}")
                                # print("-" * 20)
                            if lStart:
                                if key_num in SELECT_BUTTONS: # = SELECT (or Enter) button
                                    print("Starting the SNES gamepad test.")
                                    lStart = False
                                    continue  # ignore the "Start" button press from the main menu code.py
                            elif is_pressed:
                                if key_num in SECOND_GAMEPAD_MAP:
                                    # if my_debug:
                                    print(f"is_pressed = {is_pressed}, key_num = {key_num}")
                                    print(f"SECOND_GAMEPAD_MAP[{key_num}] = {SECOND_GAMEPAD_MAP[key_num]}")
                                    handle_key_press(key_num)
                            
                            if key_num == 8:
                                print("START pressed. Exiting test in three seconds")
                                Stop = True
                                break # out of for event loop
                        if Stop:
                            break # out of while loop
                    else:
                        print(f"Error wrong type: expected a list however received a {type(events)}")
                    
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("Ctrl+C pressed. Exiting test in three seconds")
            Stop = True
            break
        except Exception as e:
            print(f"Error: {e}")
            Stop = True
            break

    # Go back to the main code.py


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
        run_SNES_gamepad_test()
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

