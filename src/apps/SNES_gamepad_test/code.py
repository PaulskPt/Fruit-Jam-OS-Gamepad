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

--- GamepadManager.print_gamepad_map(): SECOND_GAMEPAD_MAP ---
sorted_keys_list= [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 17, 18, 19, 20]
key:  0, value: '\x1b[A'   Button A                 Up
key:  1, value: '\x1b[B'   Button B                 Down
key:  2, value: '\x1b[X'   Button X                 Left
key:  3, value: '\x1b[Y'   Button Y                 Right
key:  4, value: '\x1b[a'   D-Pad Up                 Up
key:  5, value: '\x1b[b'   D-Pad Down               Down
key:  6, value: '\x1b[d'   D-Pad Left               Left
key:  7, value: '\x1b[c'   D-Pad Right              Right
key:  8, value: '\n'       Button Start             Start
key:  9, value: '\x1b[E'   Button Select            Select
key: 11, value: '\x1b[5~'  Button Left Shoulder     Left Shoulder
key: 12, value: '\x1b[6~'  Button Right Shoulder    Right Shoulder
key: 17, value: '\x1b[A'   Joystick Up              Up
key: 18, value: '\x1b[B'   Joystick Down            Down
key: 19, value: '\x1b[D'   Joystick Left            Left
key: 20, value: '\x1b[C'   Joystick Right           Right
------------------------------------------------------------------
Press SELECT to begin the test or START to exit.
Starting the SNES gamepad test.
key_num = 4, is_pressed = True
GAMEPAD_MAP[4] = ['\x1b[a', 'D-Pad Up', 'Up']
key_num = 5, is_pressed = True
GAMEPAD_MAP[5] = ['\x1b[b', 'D-Pad Down', 'Down']
key_num = 2, is_pressed = True
GAMEPAD_MAP[2] = ['\x1b[X', 'Button X', 'Left']
key_num = 3, is_pressed = True
GAMEPAD_MAP[3] = ['\x1b[Y', 'Button Y', 'Right']
key_num = 8, is_pressed = True
GAMEPAD_MAP[8] = ['\n', 'Button Start', 'Start']
START pressed. Exiting test...
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
    GAMEPAD_MAP,        # <-- Swapped SECOND_GAMEPAD_MAP for the new master map,
    SELECT_BUTTONS,
    START_BUTTONS
)

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
        if not my_debug:
            pad.print_gamepad_map(1) # SECOND_GAMEPAD_MAP
    else:
        print(f"{game_name}No gamepad connected. Exiting...")
        Stop = True


def handle_key_press(key, map_data):
    # map_data is already the exact list for this button, e.g. ["\x1b[A", "Button A", "Up"]
    if my_debug:
        print(f"found gamepad event.key_number: {key:2d}. "
              f"ANSI Escape code: {repr(map_data[0])} = '{map_data[1]}', "
              f"button function: {map_data[2]}")
        
    # Since the main loop already verified the key and passed its data,
    # you can directly unpack or use the elements of the list safely!
    v = map_data
    
    # If you still want to execute a specific action here, you can use v[0], v[1], or v[2]


lStart = True
Stop = False

print("Press SELECT to begin the test or START to exit.")

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
                                    continue  # ignore the "SELECT" button press from the main menu code.py
                            elif is_pressed:
                                if key_num in GAMEPAD_MAP: # Was: SECOND_GAMEPAD_MAP:
                                    button_info = GAMEPAD_MAP[key_num] # Look it up exactly once!
                                    # if my_debug:
                                    print(f"key_num = {key_num}, is_pressed = {is_pressed}")
                                    print(f"GAMEPAD_MAP[{key_num}] = {button_info}")
                                    handle_key_press(key_num, button_info)
                            
                            if key_num in START_BUTTONS:
                                print("START pressed. Exiting test...")
                                Stop = True
                                break # out of for event loop
                        if Stop:
                            break # out of while loop
                    else:
                        print(f"Error wrong type: expected a list however received a {type(events)}")
                    
            time.sleep(0.1)
        except KeyboardInterrupt:
            print("Ctrl+C pressed. Exiting test...")
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

