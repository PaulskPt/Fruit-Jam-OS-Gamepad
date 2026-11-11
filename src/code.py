# SPDX-FileCopyrightText: 2025 Tim Cocks for Adafruit Industries
# SPDX-License-Identifier: MIT
# Note Paulus Schulinck (Github @PaulskPt): use CircuitPython v 10.2.1
#      2026-05-13; Adafruit Fruit Jam with rp2350b, only!
#      Newer CPY versions result in various memory and buffer allocation errors
"""
Fruit Jam OS Launcher
Refactored to use shared /lib/fj_gamepad.py module
"""

import atexit
import json
import math
import os
import sys
import time

import adafruit_imageload
import adafruit_pathlib as pathlib
import displayio
import supervisor
import terminalio
from adafruit_anchored_group import AnchoredGroup
from adafruit_anchored_tilegrid import AnchoredTileGrid
from adafruit_argv_file import read_argv, write_argv
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.bitmap_label import Label
from adafruit_display_text.text_box import TextBox
from adafruit_displayio_layout.layouts.grid_layout import GridLayout
from adafruit_fruitjam.peripherals import VALID_DISPLAY_SIZES, request_display_config
from adafruit_usb_host_mouse import find_and_init_boot_mouse
from launcher_config import LauncherConfig
from fj_gamepad import (
    GamepadManager,
    UP_BUTTONS,
    DOWN_BUTTONS,
    A_BUTTONS,
    X_BUTTONS,
    SHOULDER_LEFT_BUTTONS,
    SHOULDER_RIGHT_BUTTONS,
    HW_LEFT,
    HW_RIGHT,
)

# D-pad Left/Right for grid navigation (keeps L1/R1 free for page flipping)
MENU_LEFT = (HW_LEFT,) # Was: (HW_LEFT, 1)
MENU_RIGHT = (HW_RIGHT,) # Was: (HW_RIGHT, 0)

# Erase console history and home cursor
sys.stdout.write("\x1b[2J\x1b[H")

my_debug = False

# --- Native Argument Interception Block ---
args = read_argv(__file__)
if args is not None and len(args) > 0:
    next_code_file = args[0]
    remaining_args = args[1:] if len(args) > 1 else []

    write_argv(__file__, [])

    if remaining_args:
        write_argv(next_code_file, remaining_args)

    if my_debug:
        print(f"Handoff: Redirecting directly to clean workspace: {next_code_file}")
    supervisor.set_next_code_file(
        next_code_file,
        sticky_on_reload=False,
        reload_on_error=True,
        working_directory="/".join(next_code_file.split("/")[:-1]),
    )
    supervisor.reload()
# ------------------------------------------

if (width_config := os.getenv("CIRCUITPY_DISPLAY_WIDTH")) is not None:
    if type(width_config) is str and width_config.isdigit():
        width_config = int(width_config)
    if width_config not in [x[0] for x in VALID_DISPLAY_SIZES]:
        raise ValueError(f"Invalid display size. Must be one of: {VALID_DISPLAY_SIZES}")
    for display_size in VALID_DISPLAY_SIZES:
        if display_size[0] == width_config:
            break
else:
    display_size = (720, 400)

request_display_config(*display_size)
display = supervisor.runtime.display

launcher_config = LauncherConfig()

SCREENSAVER_TIMEOUT = launcher_config.screensaver_timeout
last_interaction_time = time.monotonic()
screensaver = None
previous_mouse_location = [0, 0]

scale = 1
if display.width > 360:
    scale = 2

font_file = "/fonts/terminal.lvfontbin"
font = bitmap_font.load_font(font_file)
scaled_group = displayio.Group(scale=scale)

main_group = displayio.Group()
main_group.append(scaled_group)

display.root_group = main_group

background_bmp = displayio.Bitmap(display.width, display.height, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = launcher_config.palette_bg
bg_tg = displayio.TileGrid(bitmap=background_bmp, pixel_shader=bg_palette)
scaled_group.append(bg_tg)

WIDTH = int(298 / 360 * display.width // scale)
HEIGHT = int(182 / 200 * display.height // scale)

my_debug = launcher_config.data.get("my_debug", False)
if my_debug:
    print(f"my_debug from launcher_conf.json = {my_debug}")
use_sound = launcher_config.data.get("use_sound", False)
use_mouse = launcher_config.data.get("use_mouse", False)
use_keyboard = launcher_config.data.get("use_keyboard", False)
use_gamepad = launcher_config.data.get("use_gamepad", False)

audio_output_fm_config = launcher_config.data.get("audio_output", "speaker")
launcher_config.audio_output = audio_output_fm_config

if my_debug:
    if use_keyboard:
        print("/code.py: Initializing Keyboard Host stack...")
    else:
        print("/code.py: Keyboard Host driver disabled. Memory optimized for application launch!")
    print("F:/CIRCUITPY/code.py: launcher_config checks:")
    print(f"launcher_config.use_mouse = {use_mouse}")
    print(f"launcher_config.use_gamepad = {use_gamepad}")
    print(f"launcher_config.use_keyboard = {use_keyboard}")
    print(f"launcher_config.use_sound = {use_sound}")
    print(f"launcher_config.audio_output = {audio_output_fm_config}")

if launcher_config.audio_output_speaker:
    launcher_config.audio_volume = 0.85
if launcher_config.audio_output_headphones:
    launcher_config.audio_volume = 0.75
if my_debug:
    print(f"audio volume set to: {str(float(launcher_config.audio_volume))}")

# 2. Mouse Engine (only if enabled in config)
mouse = None
last_left_button_state = 0
left_button_pressed = False

if use_mouse:
    mouse = find_and_init_boot_mouse()
    if mouse:
        if my_debug:
            print("Mouse found successfully!")
        mouse.scale = scale
        mouse_tg = mouse.tilegrid
        mouse_tg.x = display.width // (2 * scale)
        mouse_tg.y = display.height // (2 * scale)

# 3. Shared GamepadManager Initialization
pad = None
gamepad_bridge = None
if use_gamepad:
    try:
        import gamepad_bridge
    except Exception as e:
        if my_debug:
            print(f"failed to load gamepad_bridge: {e}")

    pad = GamepadManager(check_bridge=False, debug=my_debug)
    if pad.connected:
        pad.print_controls("Fruit-Jam-OS Launcher", (
            ("D-Pad", "Navigate apps & arrows"),
            ("L1 / R1", "Previous / Next page"),
            ("A", "Launch selected app"),
            ("X", "Edit selected app"),
        ))
        pad.wait_for_release(min_drain=0.25, timeout=1.5)
    elif my_debug:
        print("/code.py: No USB gamepad connected.")

config = {
    "menu_title": "Launcher Menu",
    "width": 3,
    "height": 2,
}

cell_width = WIDTH // config["width"]
cell_height = HEIGHT // config["height"]
page_size = config["width"] * config["height"]

default_icon_bmp, default_icon_palette = adafruit_imageload.load("launcher_assets/default_icon.bmp")
default_icon_palette.make_transparent(0)
menu_grid = GridLayout(
    x=(display.width // scale - WIDTH) // 2,
    y=(display.height // scale - HEIGHT) // 2,
    width=WIDTH,
    height=HEIGHT,
    grid_size=(config["width"], config["height"]),
    divider_lines=False,
)
scaled_group.append(menu_grid)

menu_title_txt = Label(font, text="Fruit Jam OS", color=launcher_config.palette_fg)
menu_title_txt.anchor_point = (0.5, 0.5)
menu_title_txt.anchored_position = (display.width // (2 * scale), 2)
scaled_group.append(menu_title_txt)

apps = []
app_paths = (pathlib.Path("/apps"), pathlib.Path("/sd/apps"))

for app_path in app_paths:
    if not app_path.exists():
        continue

    for path in app_path.iterdir():
        if my_debug:
            print(path)

        code_file = path / "code.py"
        if not code_file.exists():
            continue

        metadata_file = path / "metadata.json"
        if not metadata_file.exists():
            metadata = None
        else:
            with open(metadata_file.absolute()) as f:
                metadata = json.load(f)

        if metadata is not None and "icon" in metadata:
            icon_file = path / metadata["icon"]
        else:
            icon_file = path / "icon.bmp"

        if not icon_file.exists():
            icon_file = None

        if metadata is not None and "title" in metadata:
            title = metadata["title"]
        else:
            title = path.name

        apps.append(
            {
                "title": title,
                "icon": str(icon_file.absolute()) if icon_file is not None else None,
                "file": str(code_file.absolute()),
                "dir": path,
            }
        )

apps = sorted(apps, key=lambda app: app["title"].lower())
if my_debug:
    print("launcher config", launcher_config)
if len(launcher_config.favorites):
    for favorite_app in reversed(launcher_config.favorites):
        if my_debug:
            print("checking favorite", favorite_app)
        for app in apps:
            app_name = str(app["dir"].absolute()).split("/")[-1]
            if my_debug:
                print(f"checking app: {app_name}")
            if app_name == favorite_app:
                apps.remove(app)
                apps.insert(0, app)


def reuse_cell(grid_coords):
    try:
        cell_group = menu_grid.get_content(grid_coords)
        return cell_group
    except KeyError:
        return None


def _create_cell_group(app):
    cell_group = AnchoredGroup()

    if app["icon"] is None:
        icon_tg = displayio.TileGrid(bitmap=default_icon_bmp, pixel_shader=default_icon_palette)
        cell_group.append(icon_tg)
    else:
        icon_bmp, icon_palette = adafruit_imageload.load(app["icon"])
        icon_tg = displayio.TileGrid(bitmap=icon_bmp, pixel_shader=icon_palette)
        cell_group.append(icon_tg)

    icon_tg.x = cell_width // 2 - icon_tg.tile_width // 2
    title_txt = TextBox(
        font,
        text=app["title"],
        width=cell_width,
        height=18,
        align=TextBox.ALIGN_CENTER,
        color=launcher_config.palette_fg,
    )
    icon_tg.y = (cell_height - icon_tg.tile_height - title_txt.height) // 2
    cell_group.append(title_txt)
    title_txt.anchor_point = (0, 0)
    title_txt.anchored_position = (0, icon_tg.y + icon_tg.tile_height)
    return cell_group


def _reuse_cell_group(app, cell_group):
    _unhide_cell_group(cell_group)
    if app["icon"] is None:
        icon_tg = cell_group[0]
        icon_tg.bitmap = default_icon_bmp
        icon_tg.pixel_shader = default_icon_palette
    else:
        icon_bmp, icon_palette = adafruit_imageload.load(app["icon"])
        icon_tg = cell_group[0]
        icon_tg.bitmap = icon_bmp
        icon_tg.pixel_shader = icon_palette

    icon_tg.x = cell_width // 2 - icon_tg.tile_width // 2
    title_txt = cell_group[1]
    title_txt.text = app["title"]


def _hide_cell_group(cell_group):
    cell_group[0].hidden = True
    cell_group[1].text = "      "


def _unhide_cell_group(cell_group):
    cell_group[0].hidden = False

def display_page(page_index):
    max_pages = math.ceil(len(apps) / page_size)
    page_txt.text = f"{page_index + 1}/{max_pages}"

    for grid_index in range(page_size):
        grid_pos = (grid_index % config["width"], grid_index // config["width"])
        try:
            cur_app = apps[grid_index + (page_index * page_size)]
        except IndexError:
            try:
                cell_group = menu_grid.get_content(grid_pos)
                _hide_cell_group(cell_group)
            except KeyError:
                pass
            continue

        try:
            cell_group = menu_grid.get_content(grid_pos)
            _reuse_cell_group(cur_app, cell_group)
        except KeyError:
            cell_group = _create_cell_group(cur_app)
            menu_grid.add_content(cell_group, grid_position=grid_pos, cell_size=(1, 1))

        if my_debug:
            print(f"{grid_index} | {grid_index % config['width'], grid_index // config['width']}")


page_txt = Label(terminalio.FONT, text="", scale=scale, color=launcher_config.palette_fg)
page_txt.anchor_point = (1.0, 1.0)
page_txt.anchored_position = (display.width - 2, display.height - 2)
main_group.append(page_txt)

cur_page = 0
display_page(cur_page)

left_bmp, left_palette = adafruit_imageload.load("launcher_assets/arrow_left.bmp")
left_palette.make_transparent(0)
right_bmp, right_palette = adafruit_imageload.load("launcher_assets/arrow_right.bmp")
right_palette.make_transparent(0)
left_palette[2] = right_palette[2] = launcher_config.palette_arrow

left_tg = AnchoredTileGrid(bitmap=left_bmp, pixel_shader=left_palette)
left_tg.anchor_point = (0, 0.5)
left_tg.anchored_position = (0, (display.height // 2 // scale) - 2)

right_tg = AnchoredTileGrid(bitmap=right_bmp, pixel_shader=right_palette)
right_tg.anchor_point = (1.0, 0.5)
right_tg.anchored_position = ((display.width // scale), (display.height // 2 // scale) - 2)
original_arrow_btn_color = left_palette[2]

scaled_group.append(left_tg)
scaled_group.append(right_tg)

if len(apps) <= page_size:
    right_tg.hidden = True
    left_tg.hidden = True

if mouse:
    scaled_group.append(mouse_tg)

help_txt = Label(
    terminalio.FONT,
    text="[D-Pad]: Move [X]: Edit [A]: Run [L1/R1]: Page",
    color=launcher_config.palette_fg,
)
help_txt.anchor_point = (0.0, 1.0)
help_txt.anchored_position = (2, display.height - 2)

if my_debug:
    print(help_txt.bounding_box)
main_group.append(help_txt)


def atexit_callback():
    """Clean up USB devices on exit."""
    if my_debug:
        print("inside atexit callback")
    if pad is not None:
        pad.release()
    if mouse and mouse.was_attached and not mouse.device.is_kernel_driver_active(0):
        mouse.device.attach_kernel_driver(0)


atexit.register(atexit_callback)

selected = None


def change_selected(new_selected):
    global selected
    if isinstance(selected, tuple):
        menu_grid.get_content(selected)[1].background_color = None
    elif isinstance(selected, AnchoredTileGrid):
        selected.pixel_shader[2] = original_arrow_btn_color

    if isinstance(new_selected, tuple):
        menu_grid.get_content(new_selected)[1].background_color = launcher_config.palette_accent
    elif isinstance(new_selected, AnchoredTileGrid):
        new_selected.pixel_shader[2] = launcher_config.palette_accent
    selected = new_selected


change_selected((0, 0))


def page_right():
    global cur_page
    if cur_page < math.ceil(len(apps) / page_size) - 1:
        cur_page += 1
        display_page(cur_page)
        if not left_tg.hidden:
            change_selected(left_tg)


def page_left():
    global cur_page
    if cur_page > 0:
        cur_page -= 1
        display_page(cur_page)
        if not right_tg.hidden:
            change_selected(right_tg)


def handle_key_press(key):
    global index, editor_index, cur_page
    # up key
    if key == "\x1b[A":
        if isinstance(selected, tuple):
            change_selected((selected[0], (selected[1] - 1) % config["height"]))
        elif selected is left_tg:
            change_selected((0, 0))
        elif selected is right_tg:
            change_selected((2, 0))

    # down key
    elif key == "\x1b[B":
        if isinstance(selected, tuple):
            change_selected((selected[0], (selected[1] + 1) % config["height"]))
        elif selected is left_tg:
            change_selected((0, 1))
        elif selected is right_tg:
            change_selected((2, 1))

    # left key
    elif key == "\x1b[D":
        if isinstance(selected, tuple):
            if selected[0] >= 1:
                change_selected((selected[0] - 1, selected[1]))
            elif not left_tg.hidden:
                change_selected(left_tg)
            else:
                change_selected(((selected[0] - 1) % config["width"], selected[1]))
        elif selected is left_tg:
            change_selected(right_tg)
        elif selected is right_tg:
            change_selected((2, 0))

    # right key
    elif key == "\x1b[C":
        if isinstance(selected, tuple):
            if selected[0] <= 1:
                change_selected((selected[0] + 1, selected[1]))
            elif not right_tg.hidden:
                change_selected(right_tg)
            else:
                change_selected(((selected[0] + 1) % config["width"], selected[1]))
        elif selected is left_tg:
            change_selected((0, 0))
        elif selected is right_tg:
            change_selected(left_tg)

    elif key == "\n":
        if isinstance(selected, tuple):
            index = (selected[1] * config["width"] + selected[0]) + (cur_page * page_size)
            if index >= len(apps):
                index = None
            if my_debug:
                print("go!")
        elif selected is left_tg:
            page_left()
        elif selected is right_tg:
            page_right()

    elif key == "e":
        if isinstance(selected, tuple):
            editor_index = (selected[1] * config["width"] + selected[0]) + (cur_page * page_size)
            if editor_index >= len(apps):
                editor_index = None
            if my_debug:
                print("go!")

    elif key in "123456789":
        if key != "9":
            requested_page = int(key)
            max_page = math.ceil(len(apps) / page_size)
            if requested_page <= max_page:
                cur_page = requested_page - 1
                display_page(requested_page - 1)
        else:
            max_page = math.ceil(len(apps) / page_size)
            cur_page = max_page - 1
            display_page(max_page - 1)

    elif key == "\x1b[5~":
        page_left()

    elif key == "\x1b[6~":
        page_right()

    else:
        print(f"unhandled key: {repr(key)}")

if my_debug:
    print(f"apps: {apps}")
    print(f"type(mouse): {type(mouse)}")
    print(f"type(pad): {type(pad)}")

index = None
editor_index = None

while True:
    index = None
    editor_index = None
    now = time.monotonic()

    if (not mouse) and (pad is None or not pad.connected):
        available = supervisor.runtime.serial_bytes_available
        if available:
            c = sys.stdin.read(available)
            last_interaction_time = now
            if my_debug:
                print(repr(c))
            handle_key_press(c)
            last_interaction_time = now

    if mouse:
        buttons = mouse.update()

        if [mouse.x, mouse.y] != previous_mouse_location:
            last_interaction_time = now
        previous_mouse_location[0] = mouse.x
        previous_mouse_location[1] = mouse.y

        if buttons is None:
            current_left_button_state = 0
        else:
            current_left_button_state = 1 if "left" in buttons else 0

        if current_left_button_state == 1 and last_left_button_state == 0:
            left_button_pressed = True
        elif current_left_button_state == 0 and last_left_button_state == 1:
            left_button_pressed = False

        last_left_button_state = current_left_button_state

        if left_button_pressed:
            if my_debug:
                print("left click")
            last_interaction_time = now
            clicked_cell = menu_grid.which_cell_contains((mouse_tg.x, mouse_tg.y))
            if clicked_cell is not None:
                index = (clicked_cell[1] * config["width"] + clicked_cell[0]) + (
                    cur_page * page_size
                )

            if right_tg.contains((mouse_tg.x, mouse_tg.y, 0)):
                page_right()
            if left_tg.contains((mouse_tg.x, mouse_tg.y, 0)):
                page_left()

    # Poll shared GamepadManager
    if pad is not None and pad.connected:
        raw_events = pad.update()
        if raw_events:
            last_interaction_time = now

        if pad.is_any_just_pressed(UP_BUTTONS):
            handle_key_press("\x1b[A")
        if pad.is_any_just_pressed(DOWN_BUTTONS):
            handle_key_press("\x1b[B")
        if pad.is_any_just_pressed(MENU_LEFT):
            handle_key_press("\x1b[D")
        if pad.is_any_just_pressed(MENU_RIGHT):
            handle_key_press("\x1b[C")
        if pad.is_any_just_pressed(SHOULDER_LEFT_BUTTONS):
            handle_key_press("\x1b[5~")
        if pad.is_any_just_pressed(SHOULDER_RIGHT_BUTTONS):
            handle_key_press("\x1b[6~")
        if pad.is_any_just_pressed(A_BUTTONS):
            handle_key_press("\n")
        if pad.is_any_just_pressed(X_BUTTONS):
            handle_key_press("e")

    if launcher_config.screensaver_module:
        if last_interaction_time + SCREENSAVER_TIMEOUT < now:
            if display.auto_refresh:
                display.auto_refresh = False

            if screensaver is None:
                screensaver = launcher_config.get_screensaver()
                if screensaver is None:
                    raise ValueError("ScreenSaver class not found")

                request_display_config(*screensaver.display_size)
                display = supervisor.runtime.display

                if display.root_group != main_group:
                    display.root_group = main_group

            if screensaver not in main_group:
                main_group.append(screensaver)
                display.refresh()

            needs_refresh = screensaver.tick()
            if needs_refresh:
                display.refresh()

        else:
            if not display.auto_refresh:
                display.auto_refresh = True

            if screensaver in main_group:
                main_group.remove(screensaver)

            if hasattr(screensaver, "display_size"):
                request_display_config(*display_size)
                display = supervisor.runtime.display

                if display.root_group != main_group:
                    display.root_group = main_group

    if index is not None:
        if my_debug:
            print("index", index)
            print(f"selected: {apps[index]}")
        launch_file = apps[index]["file"]

        app_args = []
        if pad is not None and pad.connected and gamepad_bridge is not None:
            app_args.extend(gamepad_bridge.register_gamepad_presence())

        write_argv(launch_file, app_args)

        if mouse is not None:
            try:
                mouse.release()
            except Exception:
                pass

        if pad is not None:
            if my_debug:
                print("--- Launcher: Releasing USB Host Gamepad lock for sub-app ---")
            pad.release()

        if my_debug:
            print("--- Launcher: Disposing of graphics for reload ---")
        try:
            display.root_group = displayio.Group()
            while len(main_group) > 0:
                main_group.pop()
            while len(scaled_group) > 0:
                scaled_group.pop()
            display.refresh()
        except Exception:
            pass

        supervisor.set_next_code_file(
            launch_file,
            sticky_on_reload=False,
            reload_on_error=True,
            working_directory="/".join(launch_file.split("/")[:-1]),
        )
        supervisor.reload()

    if editor_index is not None:
        if my_debug:
            print("editor_index", editor_index)
            print(f"editor selected: {apps[editor_index]}")
        edit_file = apps[editor_index]["file"]
        editor_launch_file = "apps/editor/code.py"

        app_args = [edit_file]
        if pad is not None and pad.connected and gamepad_bridge is not None:
            app_args.extend(gamepad_bridge.register_gamepad_presence())

        write_argv(editor_launch_file, app_args)

        if mouse is not None:
            try:
                mouse.release()
            except Exception:
                pass

        if pad is not None:
            pad.release()

        try:
            display.root_group = displayio.Group()
            while len(main_group) > 0:
                main_group.pop()
            while len(scaled_group) > 0:
                scaled_group.pop()
            display.refresh()
        except Exception:
            pass

        supervisor.set_next_code_file(
            editor_launch_file,
            sticky_on_reload=False,
            reload_on_error=True,
            working_directory="/".join(editor_launch_file.split("/")[:-1]),
        )
        supervisor.reload()
