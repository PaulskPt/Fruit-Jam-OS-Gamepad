# SPDX-FileCopyrightText: 2025 John Park and Claude AI for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
# input_handler.py: CircuitPython Music Staff Application component
# Uses shared /lib/fj_gamepad.py SNES gamepad cursor & action controls
"""
import time
from adafruit_usb_host_mouse import find_and_init_boot_mouse, find_and_init_report_mouse
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    DOWN_BUTTONS,
    A_BUTTONS,
    B_BUTTONS,
    X_BUTTONS,
    Y_BUTTONS,
    SELECT_BUTTONS,
    START_BUTTONS,
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
    HW_LEFT,
    HW_RIGHT,
)

CURSOR_LEFT = (HW_LEFT, 1)
CURSOR_RIGHT = (HW_RIGHT, 0)
CURSOR_UP = UP_BUTTONS
CURSOR_DOWN = DOWN_BUTTONS

LEFT_CLICK_BUTTONS = A_BUTTONS + SELECT_BUTTONS
RIGHT_CLICK_BUTTONS = B_BUTTONS


class InputHandler:
    """Handles user input through USB mouse and/or SNES gamepad"""

    def __init__(self, screen_width, screen_height, staff_y_start, staff_height):
        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.STAFF_Y_START = staff_y_start
        self.STAFF_HEIGHT = staff_height

        cfg = LauncherConfig()
        self.use_mouse = cfg.data.get("use_mouse", False)
        self.use_gamepad = cfg.data.get("use_gamepad", True)
        self.my_debug = cfg.data.get("my_debug", False)

        # Mouse state
        self.last_left_button_state = 0
        self.last_right_button_state = 0
        self.left_button_pressed = False
        self.right_button_pressed = False
        self.mouse = None

        # Start cursor at leftmost valid staff position on 2nd line from bottom (G4)
        self.mouse_x = 30
        self.mouse_y = staff_y_start + int(staff_height * 0.75)

        # Gamepad action flags
        self.exit_requested = False
        self.undo_last_requested = False
        self.next_channel_requested = False
        self.tempo_down_requested = False
        self.tempo_up_requested = False
        
        # Debounce timers (in seconds) to prevent double-clicks from button bounce
        self.click_cooldown = 0.22
        self.last_left_click_time = 0.0
        self.last_right_click_time = 0.0

        self.pad = None
        if self.use_gamepad:
            self.pad = GamepadManager(check_bridge=True, debug=True) # was: debug=self.my_debug)
            print("DEBUG SHOULDERS:", SHOULDER_LEFT_BUTTONS, SHOULDER_RIGHT_BUTTONS)

            if self.pad.connected:
                self.pad.print_controls("Larsio Paint Music", (
                    ("D-Pad", "Move cursor (wraps top/bottom)"),
                    ("L1 / R1", "Tempo (BPM) change (-5 / +5)"),
                    ("A / SELECT", "Place note / Click button"),
                    ("B", "Erase note under cursor"),
                    ("X", "Delete last placed note"),
                    ("Y", "Cycle instrument"),
                    ("START", "Exit to main menu"),
                ))
                self.pad.wait_for_release()

    def find_mouse(self) -> bool:
        if self.use_mouse:
            self.mouse = find_and_init_boot_mouse(cursor_image=None)
            if self.mouse is None:
                self.mouse = find_and_init_report_mouse(cursor_image=None)
            if self.mouse is not None:
                self.mouse.sensitivity = 4
                return True

        if self.pad is not None and self.pad.connected:
            print("Using SNES gamepad for cursor control.")
            return True

        print("Failed to find a working mouse or gamepad")
        return False

    def process_mouse_input(self) -> bool:
        """Process combined USB mouse and SNES gamepad input."""
        current_left_button_state = 0
        current_right_button_state = 0

        if self.mouse is not None:
            buttons = self.mouse.update()
            if buttons is not None:
                if "left" in buttons:
                    current_left_button_state = 1
                if "right" in buttons:
                    current_right_button_state = 1

            self.mouse_x = self.mouse.x
            self.mouse_y = self.mouse.y

        if self.pad is not None and self.pad.connected:
            self.pad.update()

            if self.pad.is_any_just_pressed(START_BUTTONS):
                self.exit_requested = True
            if self.pad.is_any_just_pressed(X_BUTTONS):
                self.undo_last_requested = True
            if self.pad.is_any_just_pressed(Y_BUTTONS):
                self.next_channel_requested = True
            if self.pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS):
                self.tempo_down_requested = True
            if self.pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
                self.tempo_up_requested = True

            speed = 1
            if self.pad.is_any_held(CURSOR_LEFT):
                self.mouse_x -= speed
            if self.pad.is_any_held(CURSOR_RIGHT):
                self.mouse_x += speed
            if self.pad.is_any_held(CURSOR_UP):
                self.mouse_y -= speed
            if self.pad.is_any_held(CURSOR_DOWN):
                self.mouse_y += speed

            if self.pad.is_any_held(LEFT_CLICK_BUTTONS):
                current_left_button_state = 1
            if self.pad.is_any_held(RIGHT_CLICK_BUTTONS):
                current_right_button_state = 1

            if self.mouse is not None:
                self.mouse.x = self.mouse_x
                self.mouse.y = self.mouse_y

        now = time.monotonic()

        # Edge-detect + time debounce for left click (A / SELECT / Mouse Left)
        if current_left_button_state == 1 and self.last_left_button_state == 0:
            if (now - self.last_left_click_time) >= self.click_cooldown:
                self.left_button_pressed = True
                self.last_left_click_time = now
            else:
                self.left_button_pressed = False
        else:
            self.left_button_pressed = False

        # Edge-detect + time debounce for right click (B / Mouse Right)
        if current_right_button_state == 1 and self.last_right_button_state == 0:
            if (now - self.last_right_click_time) >= self.click_cooldown:
                self.right_button_pressed = True
                self.last_right_click_time = now
            else:
                self.right_button_pressed = False
        else:
            self.right_button_pressed = False

        self.last_left_button_state = current_left_button_state
        self.last_right_button_state = current_right_button_state

        # Clamp X at left/right edges, wrap Y vertically between top and bottom rows
        self.mouse_x = max(0, min(self.SCREEN_WIDTH - 1, self.mouse_x))
        if self.mouse_y < 0:
            self.mouse_y = self.SCREEN_HEIGHT - 1
        elif self.mouse_y >= self.SCREEN_HEIGHT:
            self.mouse_y = 0

        return True


    def point_in_rect(self, x, y, rect_x, rect_y, rect_width, rect_height):
        """Check if a point is inside a rectangle"""
        return (
            rect_x <= x < rect_x + rect_width
            and rect_y <= y < rect_y + rect_height
        )

    def is_over_staff(self, y):
        """Check if mouse is over the staff area"""
        return self.STAFF_Y_START <= y <= self.STAFF_Y_START + self.STAFF_HEIGHT
