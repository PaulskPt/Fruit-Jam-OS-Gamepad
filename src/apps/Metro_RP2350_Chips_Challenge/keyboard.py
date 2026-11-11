# SPDX-FileCopyrightText: 2025 Melissa LeBlanc-Williams
# SPDX-License-Identifier: MIT
# Adapted for use with a SNES-type gamepad controller by Paulus Schulinck (Github @Paulskpt) and Gemini (Google AI)
import sys
import time
import supervisor
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    DOWN_BUTTONS,
    LEFT_BUTTONS,
    RIGHT_BUTTONS,
    A_BUTTONS,
    B_BUTTONS,
    X_BUTTONS,
    Y_BUTTONS,
    START_BUTTONS,
    SELECT_BUTTONS,
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
)

# Filter L1/R1 out of D-Pad left/right so L1/R1 switch levels cleanly
DPAD_LEFT = tuple(b for b in LEFT_BUTTONS if b not in SHOULDER_LEFT_BUTTONS)
DPAD_RIGHT = tuple(b for b in RIGHT_BUTTONS if b not in SHOULDER_RIGHT_BUTTONS)


class KeyboardBuffer:
    def __init__(self, valid_sequences):
        self.key_buffer = ""
        self._valid_sequences = valid_sequences
        self._last_move_time = 0.0
        self._move_repeat_delay = 0.14

        self.pad = GamepadManager(check_bridge=False, debug=False)
        if self.pad.connected:
            self.pad.print_controls("Chip's Challenge", (
                ("D-Pad", "Move Chip"),
                ("A", "Confirm / OK"),
                ("B / START", "Pause / Resume"),
                ("Y", "Restart level"),
                ("L1 / R1", "Prev / Next level"),
                ("SELECT", "Quit to launcher"),
            ))
            self.pad.wait_for_release(min_drain=0.25, timeout=1.5)

    def update(self):
        # Poll USB serial keyboard
        while supervisor.runtime.serial_bytes_available:
            self.key_buffer += sys.stdin.read(1)

        # Poll SNES Gamepad
        if self.pad is not None and self.pad.connected:
            self.pad.update()
            now = time.monotonic()

            # Directional movement (supports both single taps and holding D-Pad)
            dir_seq = None
            if self.pad.is_any_just_pressed(UP_BUTTONS):
                dir_seq = "\x1b[A"
                self._last_move_time = now
            elif self.pad.is_any_just_pressed(DOWN_BUTTONS):
                dir_seq = "\x1b[B"
                self._last_move_time = now
            elif self.pad.is_any_just_pressed(DPAD_LEFT):
                dir_seq = "\x1b[D"
                self._last_move_time = now
            elif self.pad.is_any_just_pressed(DPAD_RIGHT):
                dir_seq = "\x1b[C"
                self._last_move_time = now
            elif now - self._last_move_time >= self._move_repeat_delay:
                if self.pad.is_any_held(UP_BUTTONS):
                    dir_seq = "\x1b[A"
                    self._last_move_time = now
                elif self.pad.is_any_held(DOWN_BUTTONS):
                    dir_seq = "\x1b[B"
                    self._last_move_time = now
                elif self.pad.is_any_held(DPAD_LEFT):
                    dir_seq = "\x1b[D"
                    self._last_move_time = now
                elif self.pad.is_any_held(DPAD_RIGHT):
                    dir_seq = "\x1b[C"
                    self._last_move_time = now

            if dir_seq is not None:
                self.key_buffer += dir_seq

            # Action & system buttons
            if self.pad.is_any_just_pressed(A_BUTTONS):
                self.key_buffer += "\n"
            if self.pad.is_any_just_pressed(B_BUTTONS):
                if "\x1b" in self._valid_sequences:
                    self.key_buffer += "\x1b"
                else:
                    self.key_buffer += " "
            if self.pad.is_any_just_pressed(START_BUTTONS):
                if "\n" in self._valid_sequences:
                    self.key_buffer += "\n"
                else:
                    self.key_buffer += " "
            if self.pad.is_any_just_pressed(X_BUTTONS):
                self.key_buffer += "\t"
            if self.pad.is_any_just_pressed(Y_BUTTONS):
                self.key_buffer += "\x12"
            if self.pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS):
                self.key_buffer += "\x10"
            if self.pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
                self.key_buffer += "\x0e"
            if self.pad.is_any_just_pressed(SELECT_BUTTONS):
                self.key_buffer += "\x11"

    def release(self):
        if self.pad is not None:
            self.pad.release()

    def print(self):
        print("buffer", end=": ")
        for key in self.key_buffer:
            print(hex(ord(key)), end=" ")

    def set_valid_sequences(self, valid_sequences):
        self._valid_sequences = valid_sequences

    def clear(self):
        self.key_buffer = ""

    def get_key(self):
        """
        Check for keyboard or gamepad input and return the first valid key sequence.
        """
        self.update()
        if self.key_buffer:
            for sequence in self._valid_sequences:
                if self.key_buffer.startswith(sequence):
                    key = sequence
                    self.key_buffer = self.key_buffer[len(sequence):]
                    return key
            self.key_buffer = self.key_buffer[1:]

        return None
