# Board: Adafruit Fruit Jam
# CircuitPython 10.1.4
# USB Gamepad style SNES test
# by Paulus Schulinck (Github handle: @PaulskPt)
# Copyright 2026
# License MIT
# Version 3

"""
Script REPL output:

Code done running.
soft reboot

Auto-reload is off.
/apps/SNES_gamepad_test/code.py output:
found gamepad event.key_number:  0. ANSI Escape code: '\x1b[A' = 'Button A', button function: Up
found gamepad event.key_number:  1. ANSI Escape code: '\x1b[B' = 'Button B', button function: Down
found gamepad event.key_number:  2. ANSI Escape code: '\x1b[X' = 'Button X', button function: Left
found gamepad event.key_number:  3. ANSI Escape code: '\x1b[Y' = 'Button Y', button function: Right
found gamepad event.key_number:  4. ANSI Escape code: '\x1b[a' = 'D-Pad Up', button function: Up
found gamepad event.key_number:  5. ANSI Escape code: '\x1b[b' = 'D-Pad Down', button function: Down
found gamepad event.key_number:  6. ANSI Escape code: '\x1b[d' = 'D-Pad Left', button function: Left
found gamepad event.key_number:  7. ANSI Escape code: '\x1b[c' = 'D-Pad Right', button function: Right
found gamepad event.key_number:  8. ANSI Escape code: '\n' = 'Button Start', button function: Start
found gamepad event.key_number:  9. ANSI Escape code: '\x1b[E' = 'Button Select', button function: Select
found gamepad event.key_number: 11. ANSI Escape code: '\x1b[5~' = 'Button Left Shoulder', button function: Left Shoulder
found gamepad event.key_number: 12. ANSI Escape code: '\x1b[6~' = 'Button Right Shoulder', button function: Right Shoulder
Exiting app in three seconds...
"""

import time
import supervisor

my_debug = False

#cur_page = 0
#index = None
#editor_index = None
gamepad = None
now = time.monotonic()

BTN_DPAD_UPDOWN_INDEX = 1
BTN_DPAD_LEFTRIGHT_INDEX = 0
BTN_ABXY_INDEX = 5
BTN_OTR_INDEX = 6

try:
    import relic_usb_host_gamepad
except ImportError:
    raise RuntimeError("relic_usb_host_gamepad library not found.\nPlease install it to use the gamepad functionality.")
else:
    gamepad = relic_usb_host_gamepad.Gamepad()
    #                                                                                            event.key_number
    GAMEPAD_MAP = {
        relic_usb_host_gamepad.BUTTON_A:      ["\x1b[A",  "Button A",              "Up"],              #  0 = Up
        relic_usb_host_gamepad.BUTTON_B:      ["\x1b[B",  "Button B",              "Down"],            #  1 = Down
        relic_usb_host_gamepad.BUTTON_X:      ["\x1b[X",  "Button X",              "Left"],            #  2 = Left
        relic_usb_host_gamepad.BUTTON_Y:      ["\x1b[Y",  "Button Y",              "Right"],           #  3 = Right
        relic_usb_host_gamepad.BUTTON_UP:     ["\x1b[a",  "D-Pad Up",              "Up"],              #  4 = D-Pad Up
        relic_usb_host_gamepad.BUTTON_DOWN:   ["\x1b[b",  "D-Pad Down",            "Down"],            #  5 = D-Pad Down
        relic_usb_host_gamepad.BUTTON_LEFT:   ["\x1b[d",  "D-Pad Left",            "Left"],            #  6 = D-Pad Left
        relic_usb_host_gamepad.BUTTON_RIGHT:  ["\x1b[c",  "D-Pad Right",           "Right"],           #  7 = D-Pad Right
        relic_usb_host_gamepad.BUTTON_START:  ["\n",      "Button Start",          "Start"],           #  8 = Enter
        relic_usb_host_gamepad.BUTTON_SELECT: ["\x1b[E",  "Button Select",         "Select"],          #  9 = Select
        relic_usb_host_gamepad.BUTTON_L1:     ["\x1b[5~", "Button Left Shoulder",  "Left Shoulder"],   # 11 = Left Shoulder button = PGUP
        relic_usb_host_gamepad.BUTTON_R1:     ["\x1b[6~", "Button Right Shoulder", "Right Shoulder"]   # 12 = Right Shoulder button = PGDN
    }

def handle_key_press(key):
    key_found = False
    # if my_debug:
    #     print(f"\nkey = {key}")
    if key in GAMEPAD_MAP: #.keys():
        # if my_debug:
        #     print(f"key {key} found")
        v = GAMEPAD_MAP[key]
        if my_debug:
            print(f"found gamepad event.key_number: {key:2d}. ANSI Escape code: {repr(v[0])} = \'{v[1]}\', button function: {v[2]}")
    else:
        if my_debug:
            print(f"unhandled key: \"{key}\"")
        else:
            pass

lStart = True

while True:
  try:
    if gamepad and gamepad.update():
        for event in gamepad.events:
            if lStart:
                if event.key_number == 8: # = Start (or Enter) button
                    lStart = False
                    continue  # ignore the "Start" button press from the main menu code.py
            elif event.pressed: # and event.key_number in GAMEPAD_MAP:
                # if_mydebug:
                #     print(f"event.pressed = {event.pressed}, event.key_number = {event.key_number}")
                #     print(f"GAMEPAD_MAP[event.key_number] = {GAMEPAD_MAP[event.key_number]}")
                last_interaction_time = time.monotonic()
                handle_key_press(event.key_number)
    time.sleep(0.1)
  except KeyboardInterrupt:
    break

# Go back to the main code.py
if my_debug:
    print("Exiting app in three seconds...\n\n")
time.sleep(3)
supervisor.reload()
