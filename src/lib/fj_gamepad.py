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
    2,
    relic_usb_host_gamepad.BUTTON_UP,
    relic_usb_host_gamepad.BUTTON_JOYSTICK_UP,
)

DOWN_BUTTONS = (
    HW_DOWN,
    3,
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
    relic_usb_host_gamepad.BUTTON_A,
)

B_BUTTONS = (
    relic_usb_host_gamepad.BUTTON_B,
)

X_BUTTONS = (
    relic_usb_host_gamepad.BUTTON_X,
)

Y_BUTTONS = (
    relic_usb_host_gamepad.BUTTON_Y,
)

SHOULDER_LEFT_BUTTONS = (11,)
#    HW_L1,                    #  removed line: relic_usb_host_gamepad.BUTTON_L1,
#)

SHOULDER_RIGHT_BUTTONS = (12,)
#    HW_R1,                     #  removed line: relic_usb_host_gamepad.BUTTON_R1,
#)


DEFAULT_GAMEPAD_MAP = {
    0: "\x1b[C",
    1: "\x1b[D",
    HW_LEFT: "\x1b[D",
    HW_RIGHT: "\x1b[C",
    HW_START: "\n",
    HW_SELECT: "\n",
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
                        print(f"RAW CONTROLLER PACKET -> Key Number: {btn} | Pressed State: {event.pressed}")
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
