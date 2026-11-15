# SPDX-FileCopyrightText: 202? ?
# SPDX-License-Identifier: MIT
# 3036-11-09 13h03 PT This lib module given by Google AI
# Note Paulus Schulinck (Github @PaulskPt): use CircuitPython v 10.2.1
#      2026-05-13; Adafruit Fruit Jam with rp2350b, only!
#      Newer CPY versions result in varios memory and buffer allocation errors
# /lib/fj_gamepad.py
import relic_usb_host_gamepad

# Physical clone hardware indexes
# Physical clone hardware indexes (081f:e401 SNES gamepad)
HW_UP = 4
HW_DOWN = 5
HW_LEFT = 6
HW_RIGHT = 7
HW_START = 8
HW_SELECT = 9
HW_L1 = 11
HW_R1 = 12

# ATTENTION ALL DEFINITIONS BELOW ARE IN TUPLES
# This means that in case there is only one element in the tuple
# there must be a comma character after the name inside the tuple !!!

# Logical action mappings (shared across apps)
LEFT_BUTTONS = (
    HW_LEFT,
    relic_usb_host_gamepad.BUTTON_LEFT,
    relic_usb_host_gamepad.BUTTON_JOYSTICK_LEFT,
    relic_usb_host_gamepad.BUTTON_L1,
)

RIGHT_BUTTONS = (
    HW_RIGHT,
    relic_usb_host_gamepad.BUTTON_RIGHT,
    relic_usb_host_gamepad.BUTTON_JOYSTICK_RIGHT,
    relic_usb_host_gamepad.BUTTON_R1,
)

UP_BUTTONS = (
    HW_UP,
    relic_usb_host_gamepad.BUTTON_UP,
    relic_usb_host_gamepad.BUTTON_JOYSTICK_UP,
)

DOWN_BUTTONS = (
    HW_DOWN,
    relic_usb_host_gamepad.BUTTON_DOWN,
    relic_usb_host_gamepad.BUTTON_JOYSTICK_DOWN,
)

SELECT_BUTTONS = (
    HW_SELECT,
    relic_usb_host_gamepad.BUTTON_SELECT,
)

START_BUTTONS = (
    HW_START,
    relic_usb_host_gamepad.BUTTON_START,
)

# Face buttons (cleanly separated from directional controls)
# see app: Larsio's Paint Music
A_BUTTONS = (
    0,
    relic_usb_host_gamepad.BUTTON_A,
)

B_BUTTONS = (
    1,
    relic_usb_host_gamepad.BUTTON_B,
)

X_BUTTONS = (
    2,
    relic_usb_host_gamepad.BUTTON_X,
)

Y_BUTTONS = (
    3,
    relic_usb_host_gamepad.BUTTON_Y,
)

SHOULDER_LEFT_BUTTONS = (11,)
#    HW_L1,                    #  removed line: relic_usb_host_gamepad.BUTTON_L1,
#)

SHOULDER_RIGHT_BUTTONS = (12,)
#    HW_R1,                     #  removed line: relic_usb_host_gamepad.BUTTON_R1,
#)


GAMEPAD_MAP = {
    0:                                            ["\n",      "Button 0",              "Enter"],
    1:                                            ["\x1b",    "Button 1",              "Escape"],
    HW_LEFT:                                      ["\x1b[D",  "Hardware Left",         "Left"],
    HW_RIGHT:                                     ["\x1b[C",  "Hardware Right",        "Right"],
    HW_START:                                     ["\n",      "Hardware Start",        "Start"],
    HW_SELECT:                                    ["\n",      "Hardware Select",       "Select"],
    relic_usb_host_gamepad.BUTTON_UP:             ["\x1b[a",  "D-Pad Up",              "Up"],
    relic_usb_host_gamepad.BUTTON_JOYSTICK_UP:    ["\x1b[A",  "Joystick Up",           "Up"],
    relic_usb_host_gamepad.BUTTON_DOWN:           ["\x1b[b",  "D-Pad Down",            "Down"],
    relic_usb_host_gamepad.BUTTON_JOYSTICK_DOWN:  ["\x1b[B",  "Joystick Down",         "Down"],
    relic_usb_host_gamepad.BUTTON_LEFT:           ["\x1b[d",  "D-Pad Left",            "Left"],
    relic_usb_host_gamepad.BUTTON_JOYSTICK_LEFT:  ["\x1b[D",  "Joystick Left",         "Left"],
    relic_usb_host_gamepad.BUTTON_RIGHT:          ["\x1b[c",  "D-Pad Right",           "Right"],
    relic_usb_host_gamepad.BUTTON_JOYSTICK_RIGHT: ["\x1b[C",  "Joystick Right",        "Right"],
    relic_usb_host_gamepad.BUTTON_A:              ["\x1b[A",  "Button A",              "Up"],
    relic_usb_host_gamepad.BUTTON_B:              ["\x1b[B",  "Button B",              "Down"],
    relic_usb_host_gamepad.BUTTON_X:              ["\x1b[X",  "Button X",              "Left"],
    relic_usb_host_gamepad.BUTTON_Y:              ["\x1b[Y",  "Button Y",              "Right"],
    relic_usb_host_gamepad.BUTTON_START:          ["\n",      "Button Start",          "Start"],
    relic_usb_host_gamepad.BUTTON_SELECT:         ["\x1b[E",  "Button Select",         "Select"],
    relic_usb_host_gamepad.BUTTON_L1:             ["\x1b[5~", "Button Left Shoulder",  "Left Shoulder"],
    relic_usb_host_gamepad.BUTTON_R1:             ["\x1b[6~", "Button Right Shoulder", "Right Shoulder"],
}

# 1. Backwards compatibility for apps importing SECOND_GAMEPAD_MAP
SECOND_GAMEPAD_MAP = GAMEPAD_MAP

# 2. Backwards compatibility for older apps expecting strings
# This dynamically maps the old dictionary name to just the string component
DEFAULT_GAMEPAD_MAP = {key: val[0] for key, val in GAMEPAD_MAP.items()}

class GamepadManager:
    def __init__(self, key_map=None, check_bridge=True, debug=False):
        self.key_map = key_map if key_map is not None else DEFAULT_GAMEPAD_MAP
        self.debug = debug
        self.gamepad = None
        self.connected = False
        self._pressed = set()
        self._just_pressed = set()
        self._just_released = set()

        if check_bridge:
            try:
                import gamepad_bridge
                if not gamepad_bridge.verify_bridged_gamepad():
                    if self.debug:
                        print("fj_gamepad: No gamepad flagged by launcher.")
                    return
            except ImportError:
                if self.debug:
                    print("fj_gamepad: gamepad_bridge not found, attempting direct init.")

        try:
            self.gamepad = relic_usb_host_gamepad.Gamepad()
            self.connected = True
            if self.debug:
                print(f"fj_gamepad: Gamepad ready ({type(self.gamepad)})")
        except Exception as e:
            if self.debug:
                print(f"fj_gamepad: Init failed: {e}")
            self.gamepad = None
            
    def class_name(self):
        return self.__class__.__name__

    def update(self):
        """Poll gamepad events. Call once per frame."""
        self._just_pressed.clear()
        self._just_released.clear()

        if self.gamepad is None:
            return []

        raw_events = []
        try:
            if self.gamepad.update():
                for event in self.gamepad.events:
                    btn = event.key_number
                    raw_events.append((btn, event.pressed))
                    if self.debug:
                        print(f"{self.__class__.__name__}.update(): RAW CONTROLLER PACKET -> Key Number: {btn} | Pressed State: {event.pressed}")
                    if event.pressed:
                        if btn not in self._pressed:
                            self._just_pressed.add(btn)
                        self._pressed.add(btn)
                    else:
                        if btn in self._pressed:
                            self._just_released.add(btn)
                        self._pressed.discard(btn)
        except Exception:
            self._just_released.update(self._pressed)
            self._pressed.clear()

        return raw_events

    def flush(self):
        """Drain any pending events in the buffer (useful for menu click-through prevention)."""
        if self.gamepad is not None:
            try:
                if self.gamepad.update():
                    for _ in self.gamepad.events:
                        pass
            except Exception:
                pass
        self._pressed.clear()
        self._just_pressed.clear()
        self._just_released.clear()

    def is_any_held(self, button_group):
        return any(btn in self._pressed for btn in button_group)

    def is_any_just_pressed(self, button_group):
        return any(btn in self._just_pressed for btn in button_group)

    def is_any_just_released(self, button_group):
        return any(btn in self._just_released for btn in button_group)

    def get_pressed_keys(self):
        return [self.key_map[btn] for btn in self._just_pressed if btn in self.key_map]

    def get_held_keys(self):
        return [self.key_map[btn] for btn in self._pressed if btn in self.key_map]

    def get_released_keys(self):
        return [self.key_map[btn] for btn in self._just_released if btn in self.key_map]
    
    def wait_for_release(self, min_drain=0.25, timeout=1.5):
        """Drain initial USB HID packets and wait until no buttons are held down."""
        import time
        if self.gamepad is None:
            return
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            self.update()
            if (time.monotonic() - start >= min_drain) and not self._pressed:
                break
            time.sleep(0.02)
        self._just_pressed.clear()
        self._just_released.clear()

    def release(self):
        """Cleanly release gamepad hardware on app exit."""
        if self.gamepad is not None:
            try:
                if hasattr(self.gamepad, "release"):
                    self.gamepad.release()
            except Exception as e:
                if self.debug:
                    print(f"Error releasing gamepad hardware: {e}")
            self.gamepad = None
            self.connected = False

    def print_controls(self, app_name, mappings):
        """Print a formatted SNES gamepad control cheat sheet to the REPL."""
        if not self.connected:
            return
        print(f"\n--- {app_name} SNES Gamepad Controls ---")
        for btn_label, action in mappings:
            print(f"  {btn_label:<10} : {action}")
        print("-" * (len(app_name) + 31) + "\n")
        

    def print_gamepad_map(self, map_idx: int = 0):
        txt0 = f"{self.class_name()}.print_gamepad_map(): "
        
        if not isinstance(map_idx, int):
            print(f"{txt0}Error: wrong parameter type. Expected: int. Received: {type(map_idx)}")
            return
        
        # 1. Select the map based on the integer index
        if map_idx == 0:
            current_map = DEFAULT_GAMEPAD_MAP
            print(f"--- {txt0}DEFAULT_GAMEPAD_MAP ---")
        elif map_idx == 1:
            current_map = SECOND_GAMEPAD_MAP
            print(f"--- {txt0}SECOND_GAMEPAD_MAP ---")
        else:
            print(f"{txt0}Error: Unknown map index {map_idx}")
            return
  
        # 2. Get and sort the keys using Adafruit's recommended way
        sorted_keys_list = sorted(list(current_map.keys()))
        print(f"sorted_keys_list= {sorted_keys_list}")
        
        # 3. Iterate through and dynamically handle strings vs lists
        for k in sorted_keys_list:
            v = current_map[k]
            
            # If the value is a list (like SECOND_GAMEPAD_MAP)
            if isinstance(v, list):
                val_str = repr(v[0]) if len(v) > 0 else ""
                name_str = v[1] if len(v) > 1 else ""
                action_str = v[2] if len(v) > 2 else ""
                print(f"key: {k:>2}, value: {val_str:<10} {name_str:<24} {action_str}")
            
            # If the value is a single raw string (like DEFAULT_GAMEPAD_MAP)
            else:
                print(f"key: {k:>2}, value: {repr(v):<10}")
        
        print("-" * 66)
