# SPDX-FileCopyrightText: 2019 Dave Astels for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
Paint for PyPortal, PyBadge, PyGamer, and the like.
Adapted for Fruit Jam OS with shared /lib/fj_gamepad.py SNES gamepad support.
"""

import gc
import sys
import time
import atexit
import supervisor
import board
import displayio
import terminalio
from adafruit_display_text import label
from launcher_config import LauncherConfig
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
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
)

try:
    from adafruit_usb_host_mouse import find_and_init_boot_mouse, find_and_init_report_mouse
    usb_available = True
except ImportError:
    usb_available = False

try:
    from adafruit_fruitjam.peripherals import request_display_config
except ImportError:
    request_display_config = None
try:
    import adafruit_touchscreen
except ImportError:
    pass
try:
    from adafruit_cursorcontrol.cursorcontrol import Cursor
    from adafruit_cursorcontrol.cursorcontrol_cursormanager import DebouncedCursorManager
except ImportError:
    pass


class Color:
    """Standard colors"""

    WHITE = 0xFFFFFF
    BLACK = 0x000000
    RED = 0xFF0000
    ORANGE = 0xFFA500
    YELLOW = 0xFFFF00
    GREEN = 0x00FF00
    BLUE = 0x0000FF
    PURPLE = 0x800080
    PINK = 0xFFC0CB

    colors = (BLACK, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, WHITE)

    def __init__(self):
        pass


################################################################################


class TouchscreenPoller:
    """Get 'pressed' and location updates from a touch screen device."""

    def __init__(self, splash, cursor_bmp):
        print("Creating a TouchscreenPoller")
        self._display_grp = splash
        self._touchscreen = adafruit_touchscreen.Touchscreen(
            board.TOUCH_XL, board.TOUCH_XR,
            board.TOUCH_YD, board.TOUCH_YU,
            calibration=((9000, 59000), (8000, 57000)),
            size=(320, 240),
        )
        self._cursor_grp = displayio.Group()
        self._cur_palette = displayio.Palette(3)
        self._cur_palette.make_transparent(0)
        self._cur_palette[1] = 0xFFFFFF
        self._cur_palette[2] = 0x000000
        self._cur_sprite = displayio.TileGrid(
            cursor_bmp, pixel_shader=self._cur_palette
        )
        self._cursor_grp.append(self._cur_sprite)
        self._display_grp.append(self._cursor_grp)
        self._x_offset = cursor_bmp.width // 2
        self._y_offset = cursor_bmp.height // 2

    def poll(self):
        p = self._touchscreen.touch_point
        if p is not None:
            self._cursor_grp.x = p[0] - self._x_offset
            self._cursor_grp.y = p[1] - self._y_offset
            return True, False, p
        return False, False, None

    def poke(self, location=None):
        self._display_grp.remove(self._cursor_grp)
        if location is not None:
            self._cursor_grp.x = location[0] - self._x_offset
            self._cursor_grp.y = location[1] - self._y_offset
        self._display_grp.append(self._cursor_grp)

    def set_cursor_bitmap(self, bmp):
        self._cursor_grp.remove(self._cur_sprite)
        self._cur_sprite = displayio.TileGrid(bmp, pixel_shader=self._cur_palette)
        self._cursor_grp.append(self._cur_sprite)
        self.poke()


################################################################################


class CursorPoller:
    """Get 'pressed' and location updates from a D-Pad/joystick device."""

    def __init__(self, splash, cursor_bmp):
        print("Creating a CursorPoller")
        self._mouse_cursor = Cursor(
            board.DISPLAY, display_group=splash, bmp=cursor_bmp, cursor_speed=2
        )
        self._x_offset = cursor_bmp.width // 2
        self._y_offset = cursor_bmp.height // 2
        self._cursor = DebouncedCursorManager(self._mouse_cursor)

    def poll(self):
        location = None
        self._cursor.update()
        a_button = self._cursor.held
        if a_button:
            location = (
                self._mouse_cursor.x + self._x_offset,
                self._mouse_cursor.y + self._y_offset,
            )
        return a_button, False, location

    def poke(self):
        self._mouse_cursor.hide()
        self._mouse_cursor.show()

    def set_cursor_bitmap(self, bmp):
        self._mouse_cursor.cursor_bitmap = bmp
        self.poke()

################################################################################


class MousePoller:
    """Get 'pressed' and location updates from a USB mouse."""

    def __init__(self, splash, cursor_bmp, screen_width, screen_height, sensitivity=3):
        print("Creating a MousePoller")
        self._display_grp = splash
        self._cursor_grp = displayio.Group()
        self._cur_palette = displayio.Palette(3)
        self._cur_palette.make_transparent(0)
        self._cur_palette[1] = 0xFFFFFF
        self._cur_palette[2] = 0x000000
        self._cur_sprite = displayio.TileGrid(
            cursor_bmp, pixel_shader=self._cur_palette
        )
        self._cursor_grp.append(self._cur_sprite)
        self._display_grp.append(self._cursor_grp)
        self._x_offset = cursor_bmp.width // 2
        self._y_offset = cursor_bmp.height // 2

        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height

        self.last_left_button_state = 0
        self.last_right_button_state = 0
        self.left_button_pressed = False
        self.right_button_pressed = False
        self.mouse = None

        self.mouse_x = screen_width // 2
        self.mouse_y = screen_height // 2
        self.sensitivity = sensitivity

        if not self.find_mouse():
            print("WARNING: Mouse not found.")

    def find_mouse(self):
        self.mouse = find_and_init_boot_mouse()
        if self.mouse is None:
            self.mouse = find_and_init_report_mouse()
            self.sensitivity = 1
        if self.mouse is None:
            return False

        fontHeight = terminalio.FONT.get_bounding_box()[1]
        self.mouse.display_size = (
            supervisor.runtime.display.width * self.sensitivity,
            (supervisor.runtime.display.height - fontHeight) * self.sensitivity,
        )
        return True

    def poll(self):
        if self.mouse is None:
            return False, False, None
        if self._process_mouse_input():
            self._cursor_grp.x = self.mouse_x - self._x_offset
            self._cursor_grp.y = self.mouse_y - self._y_offset
            return (
                self.left_button_pressed,
                self.right_button_pressed,
                (self.mouse_x, self.mouse_y),
            )
        return False, False, None

    def poke(self, location=None):
        self._display_grp.remove(self._cursor_grp)
        if location is not None:
            self._cursor_grp.x = location[0] - self._x_offset
            self._cursor_grp.y = location[1] - self._y_offset
        self._display_grp.append(self._cursor_grp)

    def set_cursor_bitmap(self, bmp):
        self._cursor_grp.remove(self._cur_sprite)
        self._cur_sprite = displayio.TileGrid(bmp, pixel_shader=self._cur_palette)
        self._cursor_grp.append(self._cur_sprite)
        self.poke()

    def _process_mouse_input(self):
        buttons = self.mouse.update()

        if buttons is None:
            current_left_button_state = 0
            current_right_button_state = 0
        else:
            current_left_button_state = 1 if "left" in buttons else 0
            current_right_button_state = 1 if "right" in buttons else 0

        if current_left_button_state == 1 and self.last_left_button_state == 0:
            self.left_button_pressed = True
        elif current_left_button_state == 0 and self.last_left_button_state == 1:
            self.left_button_pressed = False

        if current_right_button_state == 1 and self.last_right_button_state == 0:
            self.right_button_pressed = True
        elif current_right_button_state == 0 and self.last_right_button_state == 1:
            self.right_button_pressed = False

        self.last_left_button_state = current_left_button_state
        self.last_right_button_state = current_right_button_state

        self.mouse_x = max(0, min(self.SCREEN_WIDTH - 1, self.mouse.x // self.sensitivity))
        self.mouse_y = max(0, min(self.SCREEN_HEIGHT - 1, self.mouse.y // self.sensitivity))

        return True


################################################################################


class GamepadPoller:
    """Get 'pressed' and location updates from SNES gamepad via GamepadManager."""

    def __init__(self, splash, cursor_bmp, screen_width, screen_height, pad, mouse=None):
        print("Creating a GamepadPoller")
        self._display_grp = splash
        self._cursor_grp = displayio.Group()
        self._cur_palette = displayio.Palette(3)
        self._cur_palette.make_transparent(0)
        self._cur_palette[1] = 0xFFFFFF
        self._cur_palette[2] = 0x000000
        self._cur_sprite = displayio.TileGrid(
            cursor_bmp, pixel_shader=self._cur_palette
        )
        self._cursor_grp.append(self._cur_sprite)
        self._display_grp.append(self._cursor_grp)
        self._x_offset = cursor_bmp.width // 2
        self._y_offset = cursor_bmp.height // 2

        self.SCREEN_WIDTH = screen_width
        self.SCREEN_HEIGHT = screen_height
        self.pad = pad
        self.mouse = mouse
        self.sensitivity = 3

        self.cursor_x = float(screen_width // 2)
        self.cursor_y = float(screen_height // 2)
        self.cursor_speed = 2.5

        self._dpad_left = tuple(b for b in LEFT_BUTTONS if b not in SHOULDER_LEFT_BUTTONS)
        self._dpad_right = tuple(b for b in RIGHT_BUTTONS if b not in SHOULDER_RIGHT_BUTTONS)

        self.exit_requested = False
        self.toggle_brush_requested = False
        self.clear_canvas_requested = False
        self.color_step = 0

        self._cursor_grp.x = int(self.cursor_x) - self._x_offset
        self._cursor_grp.y = int(self.cursor_y) - self._y_offset

    def poll(self):
        a_pressed = False
        b_pressed = False
        self.toggle_brush_requested = False
        self.clear_canvas_requested = False
        self.color_step = 0

        if self.pad is not None and self.pad.connected:
            self.pad.update()

            if self.pad.is_any_just_pressed(START_BUTTONS):
                self.exit_requested = True

            if self.pad.is_any_just_pressed(X_BUTTONS):
                self.toggle_brush_requested = True

            if self.pad.is_any_just_pressed(Y_BUTTONS):
                self.clear_canvas_requested = True

            if self.pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS):
                self.color_step = -1

            if self.pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
                self.color_step = 1

            if self.pad.is_any_held(self._dpad_left):
                self.cursor_x = max(0.0, self.cursor_x - self.cursor_speed)
            if self.pad.is_any_held(self._dpad_right):
                self.cursor_x = min(float(self.SCREEN_WIDTH - 1), self.cursor_x + self.cursor_speed)
            if self.pad.is_any_held(UP_BUTTONS):
                self.cursor_y = max(0.0, self.cursor_y - self.cursor_speed)
            if self.pad.is_any_held(DOWN_BUTTONS):
                self.cursor_y = min(float(self.SCREEN_HEIGHT - 1), self.cursor_y + self.cursor_speed)

            a_pressed = self.pad.is_any_held(A_BUTTONS)
            b_pressed = self.pad.is_any_held(B_BUTTONS)

        if self.mouse is not None:
            buttons = self.mouse.update()
            if buttons:
                if "left" in buttons:
                    a_pressed = True
                if "right" in buttons:
                    b_pressed = True
            self.cursor_x = float(max(0, min(self.SCREEN_WIDTH - 1, self.mouse.x // self.sensitivity)))
            self.cursor_y = float(max(0, min(self.SCREEN_HEIGHT - 1, self.mouse.y // self.sensitivity)))

        loc = (int(self.cursor_x), int(self.cursor_y))
        self._cursor_grp.x = loc[0] - self._x_offset
        self._cursor_grp.y = loc[1] - self._y_offset
        return a_pressed, b_pressed, loc

    def poke(self, location=None):
        self._display_grp.remove(self._cursor_grp)
        if location is not None:
            self._cursor_grp.x = location[0] - self._x_offset
            self._cursor_grp.y = location[1] - self._y_offset
        self._display_grp.append(self._cursor_grp)

    def set_cursor_bitmap(self, bmp):
        self._cursor_grp.remove(self._cur_sprite)
        self._cur_sprite = displayio.TileGrid(bmp, pixel_shader=self._cur_palette)
        self._cursor_grp.append(self._cur_sprite)
        self.poke()

################################################################################


class Paint:  # pylint: disable=too-many-statements
    def __init__(self, display=None):

        def _cursor_bitmap_1():
            bmp = displayio.Bitmap(9, 9, 3)
            for i in range(9):
                bmp[4, i] = 1
                bmp[i, 4] = 1
            bmp[4, 4] = 0
            return bmp

        def _cursor_bitmap_3():
            bmp = displayio.Bitmap(9, 9, 3)
            for i in range(9):
                bmp[3, i] = 1
                bmp[4, i] = 1
                bmp[5, i] = 1
                bmp[i, 3] = 1
                bmp[i, 4] = 1
                bmp[i, 5] = 1
            for i in range(3, 6):
                for j in range(3, 6):
                    bmp[i, j] = 0
            return bmp

        launcher_config = LauncherConfig()
        self._debug = launcher_config.data.get("my_debug", False)
        self._use_mouse = launcher_config.data.get("use_mouse", False)
        self._use_gamepad = launcher_config.data.get("use_gamepad", True)

        if display is None:
            if request_display_config is not None:
                request_display_config(320, 240)
                display = supervisor.runtime.display
            elif hasattr(board, "DISPLAY"):
                display = board.DISPLAY
            else:
                raise RuntimeError("No display found.")

        self._display = display
        self._w = self._display.width
        self._h = self._display.height - terminalio.FONT.get_bounding_box()[1]
        self._x = self._w // 2
        self._y = self._h // 2

        self.pad = None
        if self._use_gamepad:
            self.pad = GamepadManager(check_bridge=False, debug=self._debug)
            if self.pad.connected:
                self.pad.print_controls("PyPaint", (
                    ("D-Pad", "Move cursor"),
                    ("A", "Draw / Pick color"),
                    ("B", "Flood fill"),
                    ("X", "Toggle brush size"),
                    ("Y", "Clear canvas"),
                    ("L1 / R1", "Prev / Next color"),
                    ("START", "Exit to launcher"),
                ))
                self.pad.wait_for_release(min_drain=0.25, timeout=1.5)

        self._splash = displayio.Group()

        info_text = (
            "A:Draw B:Fill X:Brush Y:Clear L1/R1:Color START:Exit"
            if (self.pad is not None and self.pad.connected)
            else "Right Click->Palette:Exit  Right Click->Canvas:Fill"
        )
        self._info_label = label.Label(
            terminalio.FONT,
            text=info_text[: self._w // 6],
            color=0xFFFFFF,
            x=0,
            y=self._h,
        )
        self._info_label.anchor_point = (0.0, 1.0)
        self._info_label.anchored_position = (2, display.height - 2)

        self._splash.append(self._info_label)

        self._bg_bitmap = displayio.Bitmap(self._w, self._h, 1)
        self._bg_palette = displayio.Palette(1)
        self._bg_palette[0] = Color.BLACK
        self._bg_sprite = displayio.TileGrid(
            self._bg_bitmap, pixel_shader=self._bg_palette, x=0, y=0
        )
        self._splash.append(self._bg_sprite)

        self._palette_bitmap = displayio.Bitmap(self._w, self._h, 8)
        self._palette_palette = displayio.Palette(len(Color.colors))
        for i, c in enumerate(Color.colors):
            self._palette_palette[i] = c
        self._palette_sprite = displayio.TileGrid(
            self._palette_bitmap, pixel_shader=self._palette_palette, x=0, y=0
        )
        self._splash.append(self._palette_sprite)

        self._fg_bitmap = displayio.Bitmap(self._w, self._h, 9)
        self._fg_palette = displayio.Palette(len(Color.colors) + 1)
        for i, c in enumerate(Color.colors):
            self._fg_palette[i] = c
        self._fg_palette[8] = Color.PINK  # Marker for filled areas
        self._fg_sprite = displayio.TileGrid(
            self._fg_bitmap, pixel_shader=self._fg_palette, x=0, y=0
        )
        self._splash.append(self._fg_sprite)

        self._number_of_palette_options = len(Color.colors) + 2
        self._swatch_height = self._h // self._number_of_palette_options
        self._swatch_width = self._w // 10

        self._palette = self._make_palette()
        self._splash.append(self._palette)

        self._display.root_group = self._splash
        try:
            gc.collect()
            self._display.refresh(target_frames_per_second=60)
        except AttributeError:
            self._display.refresh_soon()
            gc.collect()
            self._display.wait_for_frame()

        self._brush = 0
        self._cursor_bitmaps = [_cursor_bitmap_1(), _cursor_bitmap_3()]
        self.mouse = None

        if self.pad is not None and self.pad.connected:
            opt_mouse = None
            if self._use_mouse and usb_available:
                opt_mouse = find_and_init_boot_mouse()
                if opt_mouse is not None:
                    fontHeight = terminalio.FONT.get_bounding_box()[1]
                    opt_mouse.display_size = (
                        self._display.width * 3,
                        (self._display.height - fontHeight) * 3,
                    )
                    self.mouse = opt_mouse
            self._poller = GamepadPoller(
                self._splash,
                self._cursor_bitmaps[0],
                self._w,
                self._h,
                self.pad,
                mouse=opt_mouse,
            )
        elif hasattr(board, "TOUCH_XL"):
            self._poller = TouchscreenPoller(self._splash, self._cursor_bitmaps[0])
        elif hasattr(board, "BUTTON_CLOCK"):
            self._poller = CursorPoller(self._splash, self._cursor_bitmaps[0])
        elif usb_available:
            self._poller = MousePoller(self._splash, self._cursor_bitmaps[0], self._w, self._h)
            if not self._poller.mouse:
                raise RuntimeError("No gamepad or USB mouse found.")
            self.mouse = self._poller.mouse
        else:
            raise AttributeError("PyPaint requires a gamepad, mouse, touchscreen, or cursor.")

        self._a_pressed = False
        self._last_a_pressed = False
        self._b_pressed = False
        self._last_b_pressed = False
        self._location = None
        self._last_location = None

        self._pencolor = 7
        self.exit_to_launcher = False

    def _make_palette(self):
        self._palette_bitmap = displayio.Bitmap(self._w // 10, self._h, 8)
        self._palette_palette = displayio.Palette(len(Color.colors))
        for i, c in enumerate(Color.colors):
            self._palette_palette[i] = c
            for y in range(self._swatch_height):
                for x in range(self._swatch_width):
                    self._palette_bitmap[x, self._swatch_height * i + y] = i

        swatch_x_offset = (self._swatch_width - 9) // 2
        swatch_y_offset = (self._swatch_height - 9) // 2
        swatch_y = self._swatch_height * len(Color.colors) + swatch_y_offset
        for i in range(9):
            self._palette_bitmap[swatch_x_offset + 4, swatch_y + i] = 1
            self._palette_bitmap[swatch_x_offset + i, swatch_y + 4] = 1
            self._palette_bitmap[swatch_x_offset + 4, swatch_y + 4] = 0

        swatch_y += self._swatch_height
        for i in range(9):
            self._palette_bitmap[swatch_x_offset + 3, swatch_y + i] = 1
            self._palette_bitmap[swatch_x_offset + 4, swatch_y + i] = 1
            self._palette_bitmap[swatch_x_offset + 5, swatch_y + i] = 1
            self._palette_bitmap[swatch_x_offset + i, swatch_y + 3] = 1
            self._palette_bitmap[swatch_x_offset + i, swatch_y + 4] = 1
            self._palette_bitmap[swatch_x_offset + i, swatch_y + 5] = 1
        for i in range(swatch_x_offset + 3, swatch_x_offset + 6):
            for j in range(swatch_y + 3, swatch_y + 6):
                self._palette_bitmap[i, j] = 0

        for i in range(self._h):
            self._palette_bitmap[self._swatch_width - 1, i] = 7

        return displayio.TileGrid(
            self._palette_bitmap, pixel_shader=self._palette_palette, x=0, y=0
        )

    def _clear_canvas(self):
        self._fg_bitmap.fill(0)
        self._poller.poke()

    def _plot(self, x, y, c):
        r = [0] if self._brush == 0 else [-1, 0, 1]
        for i in r:
            for j in r:
                px = int(x + i)
                py = int(y + j)
                if px >= self._w // 10:
                    try:
                        self._fg_bitmap[px, py] = c
                    except IndexError:
                        pass

    def _draw_line(self, start, end):
        x0, y0 = start[0], start[1]
        x1, y1 = end[0], end[1]
        steep = abs(y1 - y0) > abs(x1 - x0)
        rev = False
        dx = x1 - x0

        if steep:
            x0, y0 = y0, x0
            x1, y1 = y1, x1
            dx = x1 - x0

        if x0 > x1:
            rev = True
            dx = x0 - x1

        dy = abs(y1 - y0)
        err = dx / 2
        ystep = 1 if y0 < y1 else -1

        while (not rev and x0 <= x1) or (rev and x1 <= x0):
            if steep:
                self._plot(int(y0), int(x0), self._pencolor)
                self._x = y0
                self._y = x0
            else:
                self._plot(int(x0), int(y0), self._pencolor)
                self._x = x0
                self._y = y0
            err -= dy
            if err < 0:
                y0 += ystep
                err += dx
            x0 = x0 - 1 if rev else x0 + 1
        self._poller.poke()

    def _fill(self, x, y, c):  # pylint: disable=too-many-branches,too-many-locals
        MARKER = 8
        if self._fg_bitmap[x, y] != c:
            blank_color = self._fg_bitmap[x, y]
            self._fg_bitmap[x, y] = MARKER
            done = False
            min_row = 0
            max_row = self._h - 1
            min_col = (self._w // 10) + 1
            max_col = self._w - 1
            while not done:
                newmin_row = self._h - 1
                newmax_row = 0
                newmin_col = self._w - 1
                newmax_col = (self._w // 10) + 1
                done = True
                for i in range(min_row, max_row):
                    for j in range(min_col, max_col):
                        if self._fg_bitmap[j, i] == MARKER:
                            newmarker = False
                            if j > self._w // 10 and self._fg_bitmap[j - 1, i] == blank_color:
                                self._fg_bitmap[j - 1, i] = MARKER
                                newmarker = True
                            if j < self._w - 1 and self._fg_bitmap[j + 1, i] == blank_color:
                                self._fg_bitmap[j + 1, i] = MARKER
                                newmarker = True
                            if i > 0 and self._fg_bitmap[j, i - 1] == blank_color:
                                self._fg_bitmap[j, i - 1] = MARKER
                                newmarker = True
                            if i < self._h - 1 and self._fg_bitmap[j, i + 1] == blank_color:
                                self._fg_bitmap[j, i + 1] = MARKER
                                newmarker = True

                            if newmarker:
                                done = False
                                if i < newmin_row:
                                    newmin_row = i
                                if i > newmax_row:
                                    newmax_row = i
                                if j < newmin_col:
                                    newmin_col = j
                                if j > newmax_col:
                                    newmax_col = j

                max_row = min(newmax_row + 2, self._h - 1)
                min_row = max(newmin_row - 2, 0)
                max_col = min(newmax_col + 2, self._w - 1)
                min_col = max(newmin_col - 2, (self._w // 10) + 1)

                self._poller.poke()

            for i in range(self._h):
                for j in range(self._w):
                    if self._fg_bitmap[j, i] == MARKER:
                        self._fg_bitmap[j, i] = c

            self._poller.poke()

    def _handle_palette_selection(self, location):
        selected = location[1] // self._swatch_height
        if selected >= self._number_of_palette_options:
            return
        if selected < len(Color.colors):
            self._pencolor = selected
        else:
            self._brush = selected - len(Color.colors)
            self._poller.set_cursor_bitmap(self._cursor_bitmaps[self._brush])

    def _handle_motion(self, start, end):
        if start[0] >= self._w // 10 and end[0] >= self._w // 10:
            self._draw_line(start, end)

    def _handle_a_press(self, location):
        if location[0] < self._w // 10:
            self._handle_palette_selection(location)
        else:
            self._plot(location[0], location[1], self._pencolor)
            self._poller.poke()

    @staticmethod
    def _handle_a_release():
        pass

    def _handle_b_release(self, location):
        if location is None:
            return
        if location[0] >= self._w // 10:
            self._fill(location[0], location[1], self._pencolor)
            self._poller.poke()
        else:
            self.exit_to_launcher = True

    @property
    def _was_a_just_pressed(self):
        return self._a_pressed and not self._last_a_pressed

    @property
    def _was_a_just_released(self):
        return not self._a_pressed and self._last_a_pressed

    @property
    def _was_b_just_released(self):
        return not self._b_pressed and self._last_b_pressed

    @property
    def _did_move(self):
        if self._location is not None and self._last_location is not None:
            return (
                self._location[0] != self._last_location[0]
                or self._location[1] != self._last_location[1]
            )
        return False

    def _update(self):
        self._last_a_pressed = self._a_pressed
        self._last_b_pressed = self._b_pressed
        if self._location is not None:
            self._last_location = self._location
        self._a_pressed, self._b_pressed, self._location = self._poller.poll()

    def run(self):
        """Run the painting program."""
        while True:
            self._update()

            if isinstance(self._poller, GamepadPoller):
                if self._poller.exit_requested:
                    self.exit_to_launcher = True
                if self._poller.toggle_brush_requested:
                    self._brush = 1 - self._brush
                    self._poller.set_cursor_bitmap(self._cursor_bitmaps[self._brush])
                if self._poller.clear_canvas_requested:
                    self._clear_canvas()
                if self._poller.color_step != 0:
                    self._pencolor = (self._pencolor + self._poller.color_step) % len(Color.colors)

            if self.exit_to_launcher:
                break

            if self._was_a_just_pressed:
                self._handle_a_press(self._location)
            elif self._was_a_just_released:
                self._handle_a_release()
            if self._was_b_just_released:
                self._handle_b_release(self._last_location)
            if self._did_move and self._a_pressed:
                self._handle_motion(self._last_location, self._location)

            time.sleep(0.02)


painter = Paint()


def atexit_callback():
    """Clean up USB devices and point next reload back to Fruit Jam OS launcher."""
    if painter.pad is not None:
        painter.pad.release()
    if painter.mouse is not None:
        mouse = painter.mouse
        try:
            mouse.release()
            if mouse.was_attached:
                while supervisor.runtime.serial_bytes_available:
                    sys.stdin.read(1)
        except Exception:
            pass
    try:
        from adafruit_argv_file import write_argv
        write_argv(__file__, [])
    except Exception:
        pass
    try:
        supervisor.runtime.display.root_group = displayio.Group()
        gc.collect()
    except Exception:
        pass
    supervisor.set_next_code_file(
        "/code.py",
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/",
    )


atexit.register(atexit_callback)

painter.run()
if painter.exit_to_launcher:
    supervisor.reload()
